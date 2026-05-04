import pytest

from .fixtures.defaults import TEST_USER_EMAIL, TEST_USER_PASSWORD
from .page_objects.bucket_view import BucketViewPage
from .page_objects.login import LoginPage


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_mark_bucket_triaged(page, live_server, e2e_data):
    login_page = LoginPage(page, live_server)
    login_page.login(TEST_USER_EMAIL, TEST_USER_PASSWORD)

    bucket_view = BucketViewPage(page, live_server, e2e_data["untriaged_bucket_id"])
    bucket_view.navigate()
    bucket_view.wait_for_loaded()

    # No triage status set yet, button reads "Mark triaged" and the status
    # display is absent.
    assert bucket_view.triage_trigger.inner_text().strip() == "Mark triaged"
    assert bucket_view.triage_status_display.count() == 0

    bucket_view.open_triage_panel()
    bucket_view.select_triage_status("worksforme")

    # After the page reloads the trigger flips and the status display appears.
    bucket_view.wait_for_loaded()
    assert bucket_view.triage_trigger.inner_text().strip() == "Change triage status"
    assert bucket_view.triage_status_label.inner_text().strip() == "Works For Me"


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_change_and_unmark_triage_status(page, live_server, e2e_data):
    login_page = LoginPage(page, live_server)
    login_page.login(TEST_USER_EMAIL, TEST_USER_PASSWORD)

    bucket_view = BucketViewPage(page, live_server, e2e_data["triaged_bucket_id"])
    bucket_view.navigate()
    bucket_view.wait_for_loaded()

    # Already has "worksforme" status
    assert bucket_view.triage_trigger.inner_text().strip() == "Change triage status"
    assert bucket_view.triage_status_label.inner_text().strip() == "Works For Me"

    # Change to a different status
    bucket_view.open_triage_panel()
    bucket_view.select_triage_status("invalid")
    bucket_view.wait_for_loaded()
    assert bucket_view.triage_status_label.inner_text().strip() == "Invalid"

    # Unmark
    bucket_view.open_triage_panel()
    bucket_view.unmark_triage()
    bucket_view.wait_for_loaded()
    assert bucket_view.triage_trigger.inner_text().strip() == "Mark triaged"
    assert bucket_view.triage_status_display.count() == 0
