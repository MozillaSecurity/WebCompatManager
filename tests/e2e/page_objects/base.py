"""Base page object class for e2e tests."""


class PageObject:
    """Base class for page objects following the Page Object pattern."""

    url = "/"

    def __init__(self, page, live_server):
        self.page = page
        self.live_server = live_server

    def navigate(self):
        """Navigate to this page's URL."""
        self.page.goto(f"{self.live_server.url}{self.url}")
