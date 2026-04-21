import pytest

from .fixtures.defaults import TEST_USER_EMAIL, TEST_USER_PASSWORD
from .page_objects.buckets import BucketsPage
from .page_objects.login import LoginPage


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_buckets_page(page, live_server, e2e_data):
    login_page = LoginPage(page, live_server)
    login_page.login(TEST_USER_EMAIL, TEST_USER_PASSWORD)

    buckets_page = BucketsPage(page, live_server)
    buckets_page.navigate()
    buckets_page.wait_for_buckets_to_load()

    expected_buckets = e2e_data["bucket_count"]
    actual_buckets = buckets_page.bucket_count()
    assert actual_buckets == expected_buckets, (
        f"Expected {expected_buckets} buckets, but found {actual_buckets}"
    )
