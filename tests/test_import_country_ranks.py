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
    def _run_command(self, client_mock, **options):
        with patch(
            "reportmanager.management.commands.import_country_ranks.bigquery.Client",
            return_value=client_mock,
        ):
            call_command("import_country_ranks", **options)

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
        BucketCountryRank.objects.create(bucket=bucket, country="germany_rank", rank=50)

        # BQ still returns data for example.com, but only for us_rank — so the
        # germany_rank row is stale and the us_rank row is fresh. Cleanup must
        # delete the former and keep the latter.
        client = make_bq_client(
            host_rows=[{"host": "example.com", "us_rank": 1}],
            rank_cols=["us_rank"],
        )
        self._run_command(client)

        assert not BucketCountryRank.objects.filter(
            bucket=bucket, country="germany_rank"
        ).exists()
        assert BucketCountryRank.objects.filter(
            bucket=bucket, country="us_rank"
        ).exists()

    def test_empty_import_does_not_delete_existing_rows(self):
        # A full import that returns no matching rows from BQ.
        bucket = make_bucket(domain="example.com")
        BucketCountryRank.objects.create(bucket=bucket, country="germany_rank", rank=50)

        # BQ returns data only for a host that isn't a bucket domain, so
        # to_upsert ends up empty.
        client = make_bq_client(
            host_rows=[{"host": "other.com", "germany_rank": 1}],
            rank_cols=["germany_rank"],
        )
        self._run_command(client)

        assert BucketCountryRank.objects.filter(
            bucket=bucket, country="germany_rank"
        ).exists()

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

    def test_looks_up_by_domain_not_domain_normalized(self):
        """A bucket for "www.youtube.com" must be matched against that exact
        host, not the www-stripped "youtube.com" (domain_normalized), since
        CrUX ranks the two hosts separately and can rank them very
        differently.
        """
        bucket = make_bucket(domain="www.youtube.com")
        assert bucket.domain_normalized == "youtube.com"

        client = make_bq_client(
            host_rows=[
                {"host": "www.youtube.com", "us_rank": 1000},
                {"host": "youtube.com", "us_rank": 5000000},
            ],
            rank_cols=["us_rank"],
        )
        self._run_command(client)

        ranks = BucketCountryRank.objects.filter(bucket=bucket)
        assert ranks.count() == 1
        assert ranks.get().rank == 1000

    def test_partial_import_looks_up_by_domain_not_domain_normalized(self):
        """The --domains path (used by triage for newly-encountered domains)
        must also match the raw domain, not the www-stripped one.
        """
        bucket = make_bucket(domain="www.youtube.com")

        client = make_bq_client(
            host_rows=[
                {"host": "www.youtube.com", "us_rank": 1000},
                {"host": "youtube.com", "us_rank": 5000000},
            ],
            rank_cols=["us_rank"],
        )
        self._run_command(client, domains=["www.youtube.com"])

        ranks = BucketCountryRank.objects.filter(bucket=bucket)
        assert ranks.count() == 1
        assert ranks.get().rank == 1000
