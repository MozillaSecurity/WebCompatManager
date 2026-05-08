import os

import pytest

from .fixtures.defaults import TEST_USER_EMAIL, TEST_USER_PASSWORD
from .fixtures.reports_data import e2e_data  # noqa: F401
from .page_objects.login import LoginPage


@pytest.fixture(scope="session", autouse=True)
def django_async_unsafe():
    """Allow Django ORM in pytest-playwright async context."""
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture()
def logged_in(page, live_server, e2e_data):
    LoginPage(page, live_server).login(TEST_USER_EMAIL, TEST_USER_PASSWORD)
