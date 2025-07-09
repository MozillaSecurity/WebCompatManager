# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from contextlib import suppress
from logging import getLogger
from urllib.parse import urlsplit

from dateutil.parser import isoparse
from django.conf import settings
from django.core.management import BaseCommand
from django.db.utils import IntegrityError
from django.utils import timezone
from google.cloud import bigquery
from google.oauth2 import service_account

from reportmanager.models import ReportEntry
from webcompat.models import Report

LOG = getLogger("reportmanager.import")


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
        result = client.query_and_wait(
            f"""SELECT r.*, t.language_code, t.translated_text
                FROM `{settings.BIGQUERY_TABLE}` as r
                LEFT JOIN `{settings.BIGQUERY_TRANSLATIONS_TABLE}` t
                    ON r.uuid = t.report_uuid
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
            )
            with suppress(IntegrityError):
                ReportEntry.objects.create_from_report(report_obj)
                created += 1
        LOG.info("imported %d report entries", created)

    def add_arguments(self, parser):
        parser.add_argument(
            "--since",
            help="date/time in ISO 8601 format",
            type=isoparse,
            required=True,
        )
