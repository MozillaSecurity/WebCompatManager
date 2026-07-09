# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import pytest
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User as DjangoUser
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from reportmanager.models import Bucket, BucketCountryRank
from reportmanager.models import User as ReportManagerUser


def make_bucket(domain="example.com"):
    return Bucket.objects.create(signature='{"symptoms": []}', domain=domain)


@pytest.fixture
def authed_client(db):
    """Create a user with read permissions and return an authenticated APIClient."""
    user = DjangoUser.objects.create_user(
        username="testuser", password="testpass", email="testuser@example.com"
    )
    ct = ContentType.objects.get_for_model(ReportManagerUser)
    for codename in ("reportmanager_visible", "reportmanager_read"):
        perm = Permission.objects.get(content_type=ct, codename=codename)
        user.user_permissions.add(perm)

    token, _ = Token.objects.get_or_create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.mark.django_db
class TestCountryRankColumnsEndpoint:
    URL = "/reportmanager/rest/country-rank-columns/"

    def test_returns_distinct_country_columns(self, authed_client):
        bucket = make_bucket()
        BucketCountryRank.objects.create(bucket=bucket, country="poland_rank", rank=10)
        BucketCountryRank.objects.create(bucket=bucket, country="us_rank", rank=20)

        response = authed_client.get(self.URL)

        assert response.status_code == 200
        assert response.json() == ["poland_rank", "us_rank"]

    def test_returns_empty_list_when_no_ranks(self, authed_client):
        response = authed_client.get(self.URL)

        assert response.status_code == 200
        assert response.json() == []

    def test_deduplicates_country_values(self, authed_client):
        bucket1 = make_bucket(domain="example.com")
        bucket2 = make_bucket(domain="other.com")
        BucketCountryRank.objects.create(bucket=bucket1, country="germany_rank", rank=1)
        BucketCountryRank.objects.create(bucket=bucket2, country="germany_rank", rank=2)
        BucketCountryRank.objects.create(bucket=bucket1, country="us_rank", rank=3)

        response = authed_client.get(self.URL)

        assert response.status_code == 200
        assert response.json() == ["germany_rank", "us_rank"]

    def test_returns_columns_sorted_alphabetically(self, authed_client):
        bucket = make_bucket()
        BucketCountryRank.objects.create(bucket=bucket, country="us_rank", rank=1)
        BucketCountryRank.objects.create(bucket=bucket, country="global_rank", rank=2)
        BucketCountryRank.objects.create(bucket=bucket, country="poland_rank", rank=3)

        response = authed_client.get(self.URL)

        assert response.status_code == 200
        assert response.json() == ["global_rank", "poland_rank", "us_rank"]

    def test_unauthenticated_returns_403(self, db):
        client = APIClient()
        response = client.get(self.URL)

        assert response.status_code in (401, 403)
