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

    # Default view excludes triaged buckets.
    expected_buckets = e2e_data["bucket_count"] - e2e_data["triaged_count"]
    actual_buckets = buckets_page.bucket_count()
    assert actual_buckets == expected_buckets, (
        f"Expected {expected_buckets} buckets, but found {actual_buckets}"
    )


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_buckets_list_show_hide_triaged(page, live_server, e2e_data):
    login_page = LoginPage(page, live_server)
    login_page.login(TEST_USER_EMAIL, TEST_USER_PASSWORD)

    buckets_page = BucketsPage(page, live_server)
    buckets_page.navigate()
    buckets_page.wait_for_buckets_to_load()

    untriaged_count = e2e_data["bucket_count"] - e2e_data["triaged_count"]
    assert buckets_page.bucket_count() == untriaged_count

    # Show Triaged - all buckets visible
    buckets_page.click_show_triaged_toggle()
    buckets_page.wait_for_buckets_to_load()
    assert buckets_page.bucket_count() == e2e_data["bucket_count"]

    # Hide Triaged again
    buckets_page.click_show_triaged_toggle()
    buckets_page.wait_for_buckets_to_load()
    assert buckets_page.bucket_count() == untriaged_count
