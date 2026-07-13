"""Tests for the country-rank filter's query semantics."""

import json

import pytest
from django.utils import timezone

from reportmanager.models import Bucket, BucketCountryRank
from reportmanager.views import json_to_query


def mkbucket(desc):
    return Bucket.objects.create(description=desc, signature="{}")


def rank(bucket, country, r):
    BucketCountryRank.objects.create(
        bucket=bucket, country=country, rank=r, updated_at=timezone.now()
    )


def run(query_str):
    _, q = json_to_query(query_str, Bucket)
    return set(Bucket.objects.filter(q).values_list("description", flat=True))


@pytest.fixture
def rank_fixture(db):
    bbc = mkbucket("www.bbc.co.uk")
    rank(bbc, "uk_rank", 1000)
    rank(bbc, "global_rank", 1000)

    less_popular = mkbucket("less-popular.co.uk")
    rank(less_popular, "uk_rank", 1000)
    rank(less_popular, "global_rank", 50000)

    example = mkbucket("example.co.uk")
    rank(example, "uk_rank", 5000)
    rank(example, "global_rank", 50000)


# The compiled JSON that the frontend CountryRankBucketFilter.toQuery emits.
def rank_clause(country, threshold):
    return {
        "op": "EXISTS",
        "relation": "country_ranks",
        "country": country,
        "rank__lte": threshold,
    }


@pytest.mark.django_db
def test_single_rank_filter(rank_fixture):
    """uk_rank:<=1000"""
    got = run(json.dumps(rank_clause("uk_rank", 1000)))
    assert got == {"www.bbc.co.uk", "less-popular.co.uk"}


@pytest.mark.django_db
def test_uk_but_not_global(rank_fixture):
    """uk_rank:<=1000 AND NOT global_rank:<=1000"""
    query = json.dumps(
        {
            "op": "AND",
            "0": rank_clause("uk_rank", 1000),
            "1": {"op": "NOT", "0": rank_clause("global_rank", 1000)},
        }
    )
    got = run(query)
    # less-popular.co.uk qualifies (global rank 50000, outside the top 1000);
    # www.bbc.co.uk is excluded because it is in the global top 1000.
    assert got == {"less-popular.co.uk"}


@pytest.mark.django_db
def test_uk_and_global(rank_fixture):
    """uk_rank:<=1000 AND global_rank:<=1000"""
    query = json.dumps(
        {
            "op": "AND",
            "0": rank_clause("uk_rank", 1000),
            "1": rank_clause("global_rank", 1000),
        }
    )
    got = run(query)
    assert got == {"www.bbc.co.uk"}
