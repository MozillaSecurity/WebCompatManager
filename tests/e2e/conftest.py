import os

import pytest

from .fixtures.reports_data import e2e_data  # noqa: F401


@pytest.fixture(scope="session", autouse=True)
def django_async_unsafe():
    """Allow Django ORM in pytest-playwright async context."""
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
