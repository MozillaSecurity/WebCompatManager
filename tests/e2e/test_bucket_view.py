import pytest

from .page_objects.bucket_view import BucketViewPage


@pytest.fixture()
def bucket_view_page(page, live_server, logged_in):
    def load(bucket_id):
        view = BucketViewPage(page, live_server, bucket_id)
        view.navigate()
        view.wait_for_loaded()
        return view

    return load


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_mark_bucket_triaged(bucket_view_page, e2e_data):
    bucket_view = bucket_view_page(e2e_data["untriaged_bucket_id"])

    # No triage status set yet, button reads "Mark triaged" and the status
    # display is absent.
    bucket_view.expect_triage_trigger("Mark triaged")
    assert bucket_view.triage_status_display.count() == 0

    bucket_view.open_triage_panel()
    bucket_view.select_triage_status("worksforme")

    bucket_view.expect_triage_trigger("Change triage status")
    bucket_view.expect_triage_label("Works For Me")


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_change_and_unmark_triage_status(bucket_view_page, e2e_data):
    bucket_view = bucket_view_page(e2e_data["triaged_bucket_id"])

    # Already has "worksforme" status
    bucket_view.expect_triage_trigger("Change triage status")
    bucket_view.expect_triage_label("Works For Me")

    # Change to a different status
    bucket_view.open_triage_panel()
    bucket_view.select_triage_status("invalid")
    bucket_view.expect_triage_label("Invalid")

    # Unmark
    bucket_view.open_triage_panel()
    bucket_view.unmark_triage()
    bucket_view.expect_triage_trigger("Mark triaged")
    assert bucket_view.triage_status_display.count() == 0
