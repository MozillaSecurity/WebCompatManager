# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Backfill missing ML classifications and translations from BigQuery.

This command queries BigQuery for ML classification results and translations
that are missing from the database and updates ReportEntry records accordingly.

Background
----------
The broken_site_report_ml ETL job in docker-etl performs two operations:
1. Gets ML classification from bugbug for each report
2. Translates reports using ML.TRANSLATE

However, some reports in the local database may be missing this data after
we import them with import_reports_from_bigquery due to failures in the ETL pipeline,
i.e. bugbug not returning classifications results or the job is stopped
for whatever reason.

By the time the ETL job receives the results, reports already might
be imported into the dashboard DB. This backfill job periodically queries
BigQuery for missing data and updates the local database.

Impact on Clustering
--------------------
Reports with ml_valid_probability=NULL are excluded from clustering entirely
and assigned to domain-based buckets.

When reports receive new ML classifications or translations, they need to be re-triaged.
All reports receiving updates have their bucket_id cleared so triage_new_reports can
reassign them to proper cluster-based or domain-based bucket.

Note: this backfill job only selecting reports with missing ML classification and
not missing translation to fetch updates for. It's possible that ML.TRANSLATE is unable
to translate text, but it's rather an edge case and mainly happens because text
is too long (i.e. entire html page contents) or contains unprocessable characters.
Once missing classification is received the job also checks if translation
was missing and updates it, however missing ML classification is the
deciding factor for updates.

"""

from dataclasses import dataclass
from itertools import batched
from logging import getLogger

from django.conf import settings
from django.core.management import BaseCommand
from google.cloud import bigquery
from google.oauth2 import service_account

from reportmanager.locking import JobLockError, acquire_job_lock
from reportmanager.models import JobLock, ReportEntry
from reportmanager.utils import preprocess_text, transform_ml_label

LOG = getLogger("reportmanager.backfill")


@dataclass
class BackfillData:
    ml_valid_probability: float | None
    language_code: str | None
    translated_text: str | None


class Command(BaseCommand):
    help = "Backfill missing ML classification and translations from BigQuery"

    BQ_BATCH_SIZE = 5000
    DB_BATCH_SIZE = 1000

    def handle(self, *args, **options) -> None:
        try:
            with acquire_job_lock(JobLock.LockTypes.BACKFILL):
                self.run_backfill()
        except JobLockError as e:
            LOG.warning(f"Cannot start backfill: {e}")
            return

    def run_backfill(self) -> None:
        # Find reports needing ML updates (only those with non-empty comments)
        reports_to_update = ReportEntry.objects.filter(
            ml_valid_probability__isnull=True, comments__isnull=False
        ).exclude(comments="")

        total_reports = reports_to_update.count()

        if total_reports == 0:
            LOG.info("No reports need ML backfill")
            return

        LOG.info("Found %d reports needing ML backfill", total_reports)

        all_reports = list(reports_to_update)
        batches = list(batched(all_reports, self.BQ_BATCH_SIZE))
        total_updated: int = 0

        params = {
            "project": settings.BIGQUERY_PROJECT,
        }

        if svc_acct := getattr(settings, "BIGQUERY_SERVICE_ACCOUNT", None):
            params["credentials"] = (
                service_account.Credentials.from_service_account_info(svc_acct)
            )

        client: bigquery.Client = bigquery.Client(**params)

        for batch_num, report_batch in enumerate(batches, 1):
            LOG.info(
                "Processing batch %d (total %d reports)...",
                batch_num,
                len(report_batch),
            )

            uuid_batch: list[str] = [str(report.uuid) for report in report_batch]

            query: str = f"""
                SELECT r.uuid,
                       c.label as ml_label, c.probability as ml_probability,
                       t.language_code, t.translated_text
                FROM `{settings.BIGQUERY_TABLE}` as r
                INNER JOIN `{settings.BIGQUERY_CLASSIFICATION_TABLE}` c
                    ON r.uuid = c.report_uuid
                LEFT JOIN `{settings.BIGQUERY_TRANSLATIONS_TABLE}` t
                    ON r.uuid = t.report_uuid
                WHERE r.uuid IN UNNEST(@uuids)
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ArrayQueryParameter("uuids", "STRING", uuid_batch)
                ]
            )

            result = client.query(query, job_config=job_config)

            bq_data: dict[str, BackfillData] = {}
            for row in result:
                ml_valid_probability = transform_ml_label(
                    row.ml_label, row.ml_probability
                )
                bq_data[row.uuid] = BackfillData(
                    ml_valid_probability=ml_valid_probability,
                    language_code=row.language_code,
                    translated_text=row.translated_text,
                )

            LOG.info("Fetched data for %d reports from BigQuery", len(bq_data))

            if not bq_data:
                continue

            reports_to_update: list[ReportEntry] = []

            for report in report_batch:
                uuid = str(report.uuid)

                if uuid in bq_data:
                    data = bq_data[uuid]
                    updated = False

                    if (
                        report.ml_valid_probability is None
                        and data.ml_valid_probability is not None
                    ):
                        report.ml_valid_probability = data.ml_valid_probability
                        updated = True

                    if (
                        report.comments_translated is None
                        and data.translated_text is not None
                    ):
                        report.comments_translated = data.translated_text
                        report.comments_original_language = data.language_code
                        report.comments_preprocessed = preprocess_text(
                            data.translated_text
                        )
                        updated = True

                    if updated:
                        reports_to_update.append(report)

                        # Clear bucket assignment to re-triage these reports
                        if report.cluster_id is None:
                            report.bucket_id = None

            if reports_to_update:
                ReportEntry.objects.bulk_update(
                    reports_to_update,
                    [
                        "ml_valid_probability",
                        "comments_translated",
                        "comments_original_language",
                        "comments_preprocessed",
                        "bucket_id",
                    ],
                    batch_size=self.DB_BATCH_SIZE,
                )
                total_updated += len(reports_to_update)
                LOG.info(
                    "Updated %d reports in batch (cleared buckets for re-triaging)",
                    len(reports_to_update),
                )

        LOG.info("Backfill complete: %d reports updated", total_updated)
