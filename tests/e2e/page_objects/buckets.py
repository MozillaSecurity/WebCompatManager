from .base import PageObject


class BucketsPage(PageObject):
    """Page object for the buckets list page."""

    url = "/reportmanager/buckets/"

    def __init__(self, page, live_server):
        super().__init__(page, live_server)

        self.bucket_items = self.page.get_by_test_id("bucket-row")
        self.show_all = self.page.get_by_test_id("all")
        self.show_needs_triage = self.page.get_by_test_id("needs_triage")
        self.show_triaged = self.page.get_by_test_id("triaged")
        self.query_input = self.page.get_by_test_id("query-input")
        self.query_error = self.page.get_by_test_id("query-error")

    def bucket_count(self):
        """Return the number of buckets displayed on the page."""
        return self.bucket_items.count()

    def wait_for_buckets_to_load(self):
        """Wait for bucket rows to appear on the page."""
        self.bucket_items.first.wait_for(state="visible")

    def click_on_state(self, locator):
        with self.page.expect_response(
            lambda r: "/reportmanager/rest/buckets/" in r.url
            and r.request.method == "GET"
        ):
            locator.click()

    def click_show_all(self):
        """Click All button to show all buckets including triaged."""
        self.click_on_state(self.show_all)

    def click_needs_triage(self):
        """Click Needs Triage to hide triaged buckets."""
        self.click_on_state(self.show_needs_triage)

    def click_triaged(self):
        """Click Triaged to show only triaged buckets."""
        self.click_on_state(self.show_triaged)

    def search_query(self, text):
        """Type a complete query into the typed filter field and run it.

        Pressing Enter submits the query directly.
        """
        self.query_input.fill(text)
        with self.page.expect_response(
            lambda r: "/reportmanager/rest/buckets/" in r.url
            and r.request.method == "GET"
        ):
            self.query_input.press("Enter")
