from playwright.sync_api import expect

from .base import PageObject


class BucketViewPage(PageObject):
    """Page object for an individual bucket's detail page."""

    def __init__(self, page, live_server, bucket_id):
        super().__init__(page, live_server)
        self.bucket_id = bucket_id
        self.url = f"/reportmanager/buckets/{bucket_id}/"

        self.triage_trigger = self.page.get_by_test_id("triage-trigger")
        self.triage_panel = self.page.get_by_test_id("triage-panel")
        self.triage_status_display = self.page.get_by_test_id("triage-status-display")
        self.triage_status_label = self.page.get_by_test_id("triage-status-label")
        self.unmark_option = self.page.get_by_test_id("triage-unmark")

    def wait_for_loaded(self):
        """Wait for the bucket view's triage trigger to be visible."""
        self.triage_trigger.wait_for(state="visible")

    def open_triage_panel(self):
        self.triage_trigger.click()
        self.triage_panel.wait_for(state="visible")

    def select_triage_status(self, status_value):
        """Select a triage status option by its value (e.g. 'worksforme')."""
        self.page.get_by_test_id(f"triage-option-{status_value}").click()
        self.triage_panel.wait_for(state="hidden")

    def unmark_triage(self):
        self.unmark_option.click()
        self.triage_panel.wait_for(state="hidden")

    def expect_triage_label(self, text):
        expect(self.triage_status_label).to_have_text(text)

    def expect_triage_trigger(self, text):
        expect(self.triage_trigger).to_have_text(text)
