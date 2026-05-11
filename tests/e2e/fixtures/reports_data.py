import pytest
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User as DjangoUser
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

from reportmanager.models import Bucket
from reportmanager.models import User as ReportManagerUser

from .defaults import TEST_USER_EMAIL, TEST_USER_PASSWORD


@pytest.fixture(scope="function")
def e2e_data(db):
    call_command("loaddata", "tests/e2e/fixtures/fixtures.json", verbosity=0)

    user, _ = DjangoUser.objects.get_or_create(
        username=TEST_USER_EMAIL,
        defaults={
            "email": TEST_USER_EMAIL,
            "password": make_password(TEST_USER_PASSWORD),
        },
    )
    write_perm = Permission.objects.get(
        content_type=ContentType.objects.get_for_model(ReportManagerUser),
        codename="reportmanager_write",
    )
    user.user_permissions.add(write_perm)

    return {
        "bucket_count": Bucket.objects.count(),
        "triaged_bucket_id": Bucket.objects.filter(triage_status__isnull=False)
        .order_by("id")
        .first()
        .id,
        "untriaged_bucket_id": Bucket.objects.filter(triage_status__isnull=True)
        .order_by("id")
        .first()
        .id,
        "triaged_count": Bucket.objects.filter(triage_status__isnull=False).count(),
    }
