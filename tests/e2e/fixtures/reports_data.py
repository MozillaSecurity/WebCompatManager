import pytest
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command

from reportmanager.models import Bucket

from .defaults import TEST_USER_EMAIL, TEST_USER_PASSWORD


@pytest.fixture(scope="function")
def e2e_data(db):
    call_command("loaddata", "tests/e2e/fixtures/fixtures.json", verbosity=0)

    DjangoUser.objects.get_or_create(
        username=TEST_USER_EMAIL,
        defaults={
            "email": TEST_USER_EMAIL,
            "password": make_password(TEST_USER_PASSWORD),
        },
    )

    return {"bucket_count": Bucket.objects.count()}
