from .base import PageObject


class BucketsPage(PageObject):
    """Page object for the buckets list page."""

    url = "/reportmanager/buckets/"

    def __init__(self, page, live_server):
        super().__init__(page, live_server)

        self.bucket_items = self.page.get_by_test_id("bucket-row")
        self.show_triaged_toggle = self.page.get_by_test_id("show-triaged-toggle")

    def bucket_count(self):
        """Return the number of buckets displayed on the page."""
        return self.bucket_items.count()

    def wait_for_buckets_to_load(self):
        """Wait for bucket rows to appear on the page."""
        self.bucket_items.first.wait_for(state="visible")

    def click_show_triaged_toggle(self):
        """Toggle between Show Triaged / Hide Triaged."""
        with self.page.expect_response(
            lambda r: "/reportmanager/rest/buckets/" in r.url
            and r.request.method == "GET"
        ):
            self.show_triaged_toggle.click()
