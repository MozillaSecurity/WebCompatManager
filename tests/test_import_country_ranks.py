# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command

from reportmanager.models import Bucket, BucketCountryRank


def make_bucket(domain: str | None = None) -> Bucket:
    return Bucket.objects.create(signature='{"symptoms": []}', domain=domain)


def make_bq_client(host_rows: list[dict], rank_cols: list[str]) -> MagicMock:
    """Build a mock BigQuery client for the single CRUX_DATASET() query.

    The command now issues one query (SELECT * EXCEPT (yyyymm) ... WHERE yyyymm =
    CRUX_DATASET()) whose result carries both .schema and row iteration.
    """
    schema_fields = []
    for col in ["host"] + rank_cols:
        f = MagicMock()
        f.name = col
        schema_fields.append(f)

    def make_row(data: dict) -> MagicMock:
        row = MagicMock()
        row.__getitem__ = lambda self, key: data.get(key)
        return row

    result = MagicMock()
    result.schema = schema_fields
    result.__iter__ = lambda self: iter([make_row(r) for r in host_rows])

    client = MagicMock()
    # The command calls client.query(sql, job_config=...).result()
    client.query.return_value.result.return_value = result
    return client




@pytest.mark.django_db
class TestImportCountryRanks:
    def _run_command(self, client_mock):
        with patch(
            "reportmanager.management.commands.import_country_ranks.bigquery.Client",
            return_value=client_mock,
        ):
            call_command("import_country_ranks")

    def test_creates_ranks_for_matching_bucket(self):
        bucket = make_bucket(domain="example.com")
        client = make_bq_client(
            host_rows=[{"host": "example.com", "poland_rank": 100, "us_rank": 200}],
            rank_cols=["poland_rank", "us_rank"],
        )
        self._run_command(client)

        ranks = BucketCountryRank.objects.filter(bucket=bucket)
        assert ranks.count() == 2
        poland = ranks.get(country="poland_rank")
        assert poland.rank == 100
        us = ranks.get(country="us_rank")
        assert us.rank == 200

    def test_no_rank_created_for_unmatched_bucket(self):
        make_bucket(domain="other.com")
        client = make_bq_client(
            host_rows=[{"host": "example.com", "poland_rank": 100, "us_rank": 200}],
            rank_cols=["poland_rank", "us_rank"],
        )
        self._run_command(client)

        assert BucketCountryRank.objects.count() == 0

    def test_stale_rows_are_deleted(self):
        bucket = make_bucket(domain="example.com")
        # Pre-create a stale row for a domain that is no longer in BQ
        BucketCountryRank.objects.create(
            bucket=bucket, country="germany_rank", rank=50
        )

        # BQ data no longer contains example.com at all
        client = make_bq_client(
            host_rows=[{"host": "other.com", "germany_rank": 1}],
            rank_cols=["germany_rank"],
        )
        self._run_command(client)

        assert not BucketCountryRank.objects.filter(bucket=bucket).exists()

    def test_rank_is_updated_when_changed(self):
        bucket = make_bucket(domain="example.com")
        existing = BucketCountryRank.objects.create(
            bucket=bucket, country="us_rank", rank=999
        )
        old_updated_at = existing.updated_at

        client = make_bq_client(
            host_rows=[{"host": "example.com", "us_rank": 42}],
            rank_cols=["us_rank"],
        )
        self._run_command(client)

        existing.refresh_from_db()
        assert existing.rank == 42
        assert existing.updated_at >= old_updated_at

    def test_null_ranks_are_skipped(self):
        bucket = make_bucket(domain="example.com")
        client = make_bq_client(
            host_rows=[{"host": "example.com", "poland_rank": None, "us_rank": 10}],
            rank_cols=["poland_rank", "us_rank"],
        )
        self._run_command(client)

        ranks = BucketCountryRank.objects.filter(bucket=bucket)
        assert ranks.count() == 1
        assert ranks.get().country == "us_rank"

    def test_bucket_without_domain_is_skipped(self):
        make_bucket(domain=None)
        client = make_bq_client(
            host_rows=[{"host": "example.com", "us_rank": 10}],
            rank_cols=["us_rank"],
        )
        self._run_command(client)

        assert BucketCountryRank.objects.count() == 0
