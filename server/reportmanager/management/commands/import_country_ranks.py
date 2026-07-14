# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from logging import getLogger
from uuid import uuid4

from django.conf import settings
from django.core.management import BaseCommand
from django.db import connection, transaction
from django.utils import timezone
from google.cloud import bigquery
from google.oauth2 import service_account

from reportmanager.models import Bucket, BucketCountryRank

LOG = getLogger("reportmanager.import_country_ranks")


class Command(BaseCommand):
    help = "Import CrUX country rank data from BigQuery into BucketCountryRank"

    def add_arguments(self, parser):
        parser.add_argument(
            "--bq-project",
            default=None,
            help="Override the BigQuery project (default: settings.BIGQUERY_PROJECT)",
        )
        parser.add_argument(
            "--domains",
            nargs="+",
            default=None,
            help="Limit import to these specific domains. If omitted, imports for all bucket domains.",
        )

    def handle(
        self, bq_project: str | None, domains: list[str] | None, **options: object
    ) -> None:
        project = bq_project or settings.BIGQUERY_PROJECT

        params: dict = {"project": project}
        if svc_acct := getattr(settings, "BIGQUERY_SERVICE_ACCOUNT", None):
            params["credentials"] = (
                service_account.Credentials.from_service_account_info(
                    svc_acct,
                    scopes=[
                        "https://www.googleapis.com/auth/bigquery",
                        "https://www.googleapis.com/auth/drive",
                    ],
                )
            )

        client = bigquery.Client(**params)
        crux_dataset_fn = f"`{project}.webcompat_knowledge_base.CRUX_DATASET`"

        partial = domains is not None
        if partial:
            domains = list({nd for d in domains if (nd := d.strip().lower())})
            # Only import for buckets that don't already have rank data.
            buckets = list(
                Bucket.objects.filter(
                    domain__in=domains, country_ranks__isnull=True
                ).only("id", "domain")
            )
        else:
            # Default: import for all bucket domains.
            buckets = list(
                Bucket.objects.exclude(domain__isnull=True)
                .exclude(domain="")
                .only("id", "domain")
            )

        if not buckets:
            LOG.info("No buckets with a domain — nothing to import")
            return

        domains = [b.domain for b in buckets]

        LOG.info("Querying ranks for %d bucket domains", len(domains))

        query = (
            f"SELECT * EXCEPT (yyyymm) "
            f"FROM `{project}.crux_imported.host_min_ranks` "
            f"WHERE yyyymm = {crux_dataset_fn}() "
            f"AND host IN UNNEST(@domains)"
        )
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("domains", "STRING", domains)
            ]
        )
        rows = client.query(query, job_config=job_config).result()

        # Discover rank columns from result schema (anything ending in _rank)
        rank_cols = [f.name for f in rows.schema if f.name.endswith("_rank")]

        if not rank_cols:
            LOG.warning("No rank columns found in host_min_ranks result schema")
            return

        LOG.info("Found %d rank columns: %s", len(rank_cols), rank_cols)

        # Build host -> {country_col: rank} dict (skip NULL ranks)
        host_ranks: dict[str, dict[str, int]] = {}
        for row in rows:
            host = row["host"]
            ranks = {col: row[col] for col in rank_cols if row[col] is not None}
            if ranks:
                host_ranks[host] = ranks

        LOG.info("Loaded rank data for %d hosts", len(host_ranks))

        now = timezone.now()
        import_id = uuid4()
        to_upsert: list[BucketCountryRank] = []

        for bucket in buckets:
            ranks = host_ranks.get(bucket.domain)
            if ranks:
                for country, rank in ranks.items():
                    to_upsert.append(
                        BucketCountryRank(
                            bucket_id=bucket.id,
                            country=country,
                            rank=rank,
                            updated_at=now,
                            import_id=import_id,
                        )
                    )

        # Upsert on the (bucket, country) unique constraint so existing rows
        # are updated in place rather than recreated.
        #
        # An upsert needs to know which unique constraint to treat as a
        # "conflict" (the conflict target) so it can update that row instead
        # of erroring. SQLite require unique_fields to name it.
        # MySQL uses ON DUPLICATE KEY UPDATE, which has no target
        # and simply updates on whichever unique index the new row collides
        # with, so it rejects unique_fields. For BucketCountryRank this
        # is (bucket, country) and it's the only unique key a new row can hit,
        # since the PK is auto-increment and never supplied.
        upsert_kwargs: dict = {
            "update_conflicts": True,
            "update_fields": ["rank", "updated_at", "import_id"],
        }
        if connection.features.supports_update_conflicts_with_target:
            upsert_kwargs["unique_fields"] = ["bucket", "country"]

        if not partial and not to_upsert:
            LOG.error("Full import produced 0 rows — skipping cleanup")
            return

        batch_size = 1000
        deleted_count = 0
        with transaction.atomic():
            for i in range(0, len(to_upsert), batch_size):
                batch = to_upsert[i : i + batch_size]
                BucketCountryRank.objects.bulk_create(batch, **upsert_kwargs)

            # Only clean up stale rows on a full import. The partial (--domains)
            # path only fills in missing data, so there's nothing to clean up.
            if not partial:
                deleted_count, _ = BucketCountryRank.objects.exclude(
                    import_id=import_id
                ).delete()

        LOG.info(
            "import_country_ranks complete: %d rank columns, %d buckets processed, "
            "%d rows upserted, %d stale rows deleted",
            len(rank_cols),
            len(buckets),
            len(to_upsert),
            deleted_count,
        )
