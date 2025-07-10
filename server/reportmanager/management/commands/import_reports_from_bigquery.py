# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from contextlib import suppress
from logging import getLogger
from urllib.parse import urlsplit

from dateutil.parser import isoparse
from django.conf import settings
from django.core.management import BaseCommand
from django.db.models import Q
from django.db.utils import IntegrityError
from django.utils import timezone
from google.cloud import bigquery
from google.oauth2 import service_account

from reportmanager.models import Bucket, ReportEntry
from webcompat.models import Report

LOG = getLogger("reportmanager.import")

# Little dict that maps hostnames to bucket IDs, used to memoize the results of
# the find_bucket_for_report function below, since DB lookups are slow.
KNOWN_BUCKET_IDS: dict[str, int] = {}


# This is only returning a bucket if there is exactly one matching bucket, or
# if there is absolutely no matching bucket and we have to create one. If there
# are multiple buckets matching, we return none, and effectively leave the
# report in the "untriaged", i.e. not assigned to any bucket, state. The cronjob
# can then pick the report up and run the more comprehensive full-signature
# check.
def find_bucket_for_report(report_info: Report) -> int | None:
    hostname = report_info.url.hostname
    if (known_bucket := KNOWN_BUCKET_IDS.get(hostname)) is not None:
        return known_bucket

    candidates = Bucket.objects.filter(Q(domain=hostname)).values_list("id", flat=True)

    if len(candidates) == 1:
        KNOWN_BUCKET_IDS[hostname] = candidates[0]
        return candidates[0]

    if len(candidates) == 0:
        bucket = Bucket.objects.create(
            description=f"domain is {report_info.url.hostname}",
            signature=report_info.create_signature().raw_signature,
        )
        KNOWN_BUCKET_IDS[hostname] = bucket.id
        return bucket.id

    return None


class Command(BaseCommand):
    help = "Import reports from BigQuery"

    def handle(self, *args, **options):
        created = 0
        params = {
            "project": settings.BIGQUERY_PROJECT,
        }
        if svc_acct := getattr(settings, "BIGQUERY_SERVICE_ACCOUNT", None):
            params["credentials"] = (
                service_account.Credentials.from_service_account_info(svc_acct)
            )

        client = bigquery.Client(**params)

        # For importing, we ignore reports that have a NULL URL or comment.
        # These shouldn't even exist, but we have quite a few rows like that
        # anyway. Since they're most likely just broken reports, we don't care.
        result = client.query(
            f"""SELECT
                    r.*, t.language_code, t.translated_text,
                    c.label as ml_label, c.probability as ml_probability
                FROM `{settings.BIGQUERY_TABLE}` as r
                LEFT JOIN `{settings.BIGQUERY_TRANSLATIONS_TABLE}` t
                    ON r.uuid = t.report_uuid
                LEFT JOIN `{settings.BIGQUERY_CLASSIFICATION_TABLE}` c
                    ON r.uuid = c.report_uuid
                WHERE r.url IS NOT NULL
                    AND r.comments IS NOT NULL
                    AND r.reported_at >= @since;""",
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("since", "DATETIME", options["since"])
                ]
            ),
        )

        for row in result:
            # The BugBot ML prediction can assign two labels, invalid or valid,
            # with a probability between 0 and 1. Having two labels makes
            # filtering and sorting harder, so let's transform "invalid 95%"
            # into "valid 5%".
            # There is a rare chance that a bug will have no score. In this case,
            # we just assign None, which will get treated as invalid in the
            # frontend.
            ml_valid_probability = None
            match row.ml_label:
                case "invalid":
                    ml_valid_probability = 1 - row.ml_probability
                case "valid":
                    ml_valid_probability = row.ml_probability

            report_obj = Report(
                app_name=row.app_name,
                app_channel=row.app_channel,
                app_version=row.app_version,
                breakage_category=row.breakage_category,
                comments=row.comments,
                comments_translated=row.translated_text,
                comments_original_language=row.language_code,
                details=row.details,
                reported_at=row.reported_at.replace(tzinfo=timezone.utc),
                url=urlsplit(row.url),
                os=row.os,
                uuid=row.uuid,
                ml_valid_probability=ml_valid_probability,
            )
            with suppress(IntegrityError):
                ReportEntry.objects.create_from_report(
                    report_obj, find_bucket_for_report(report_obj)
                )
                created += 1
        LOG.info("imported %d report entries", created)

    def add_arguments(self, parser):
        parser.add_argument(
            "--since",
            help="date/time in ISO 8601 format",
            type=isoparse,
            required=True,
        )
