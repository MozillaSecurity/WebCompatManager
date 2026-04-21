from .base import PageObject


class LoginPage(PageObject):
    """Page object for the login page."""

    url = "/login/"

    def __init__(self, page, live_server):
        super().__init__(page, live_server)

        self.username_input = self.page.get_by_role("textbox", name="Username")
        self.password_input = self.page.get_by_role("textbox", name="Password")
        self.submit_button = self.page.get_by_role("button", name="Login")

    def login(self, email, password):
        self.navigate()
        self.username_input.fill(email)
        self.password_input.fill(password)
        self.submit_button.click()
        self.page.wait_for_load_state("networkidle")

        assert not self.page.url.endswith("/login/"), (
            f"Login failed: still on login page ({self.page.url})"
        )
