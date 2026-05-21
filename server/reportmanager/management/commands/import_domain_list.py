# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from logging import getLogger

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from google.cloud import bigquery
from google.oauth2 import service_account

from reportmanager.models import DomainEntry, DomainSource
from reportmanager.utils import normalize_domain

LOG = getLogger("reportmanager.import_domain_list")


def sync_domain_source(
    domain_source: DomainSource, domains: set[str]
) -> tuple[int, int]:
    existing = set(domain_source.entries.values_list("domain", flat=True))
    to_add = domains - existing
    to_remove = existing - domains

    domain_source.entries.filter(domain__in=to_remove).delete()
    DomainEntry.objects.bulk_create(
        [DomainEntry(domain_source=domain_source, domain=d) for d in to_add],
        batch_size=1000,
        ignore_conflicts=True,
    )
    domain_source.last_synced_at = timezone.now()
    domain_source.save(update_fields=["last_synced_at"])

    return len(to_add), len(to_remove)


class Command(BaseCommand):
    help = "Import a named domain list from BigQuery"

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            required=True,
            help="Name of the domain source as configured in settings.BIGQUERY_DOMAIN_SOURCES",
        )

    def handle(self, *args: object, **options: object) -> None:
        name = options["name"]
        sources = getattr(settings, "BIGQUERY_DOMAIN_SOURCES", [])
        config = next((source for source in sources if source["name"] == name), None)

        if config is None:
            raise CommandError(
                f"No domain list named '{name}' found in settings.BIGQUERY_DOMAIN_SOURCES"
            )

        bq_source_field = config["bq_source_field"]

        params = {"project": settings.BIGQUERY_PROJECT}
        if svc_acct := getattr(settings, "BIGQUERY_SERVICE_ACCOUNT", None):
            params["credentials"] = (
                service_account.Credentials.from_service_account_info(svc_acct)
            )

        client = bigquery.Client(**params)
        full_table = f"{settings.BIGQUERY_PROJECT}.{config['bq_table']}"

        result = client.query(f"SELECT `{bq_source_field}` FROM `{full_table}`")

        should_normalize = config.get("normalize", False)
        domains = set()

        for row in result:
            value = row[bq_source_field]
            if should_normalize:
                value = normalize_domain(value)
            if value:
                domains.add(value)

        with transaction.atomic():
            domain_source, _ = DomainSource.objects.update_or_create(
                name=name,
                defaults={
                    "bq_table": config["bq_table"],
                    "bq_source_field": bq_source_field,
                },
            )
            added, removed = sync_domain_source(domain_source, domains)

        LOG.info(
            "Synced source '%s': %d added, %d removed, %d total",
            name,
            added,
            removed,
            len(domains),
        )
