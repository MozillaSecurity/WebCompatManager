from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from reportmanager.locking import JobLockError, acquire_lock, release_lock
from reportmanager.models import JobLock


@pytest.mark.django_db
class TestJobLocking:
    """Tests for job locking mechanism."""

    def test_acquire_free_lock(self):
        """Test acquiring a lock when it's free."""
        assert acquire_lock(JobLock.LockTypes.CLUSTERING) is True

        lock = JobLock.objects.first()
        assert lock.lock_name == JobLock.LockTypes.CLUSTERING
        assert lock.acquired_at is not None
        assert lock.acquired_by

    def test_acquire_lock_when_held(self):
        """Test that acquiring fails when lock is already held."""
        acquire_lock(JobLock.LockTypes.CLUSTERING)

        with pytest.raises(JobLockError, match=r"another operation.*is in progress"):
            acquire_lock(JobLock.LockTypes.CLEANUP)

    def test_acquire_stale_lock(self):
        """Test that stale locks are automatically released and reacquired."""
        lock = JobLock.objects.first()
        stale_time = timezone.now() - timedelta(hours=4)
        lock.lock_name = JobLock.LockTypes.CLEANUP
        lock.acquired_at = stale_time
        lock.acquired_by = "old-host:123"
        lock.save()

        assert acquire_lock(JobLock.LockTypes.CLUSTERING) is True

        lock.refresh_from_db()
        assert lock.lock_name == JobLock.LockTypes.CLUSTERING
        assert lock.acquired_at > stale_time

    def test_release_lock(self):
        """Test releasing a held lock."""
        acquire_lock(JobLock.LockTypes.CLUSTERING)
        release_lock(JobLock.LockTypes.CLUSTERING)

        lock = JobLock.objects.first()
        assert lock.lock_name == ""
        assert lock.acquired_at is None
        assert lock.acquired_by == ""

    def test_release_wrong_lock(self):
        """Test that releasing wrong lock name is handled gracefully."""
        acquire_lock(JobLock.LockTypes.CLUSTERING)
        release_lock(JobLock.LockTypes.CLEANUP)

        lock = JobLock.objects.first()
        assert lock.lock_name == JobLock.LockTypes.CLUSTERING
        assert lock.acquired_at is not None

    def test_release_unlocked(self):
        """Test that releasing when not locked is handled gracefully."""
        lock = JobLock.objects.first()
        assert lock.acquired_at is None

        release_lock(JobLock.LockTypes.CLUSTERING)

    def test_is_stale_when_unlocked(self):
        """Test that unlocked lock is not considered stale."""
        lock = JobLock.objects.first()
        lock.acquired_at = None
        assert lock.is_stale() is False

    def test_is_stale_when_recent(self):
        """Test that recently acquired lock is not stale."""
        lock = JobLock.objects.first()
        lock.acquired_at = timezone.now()
        assert lock.is_stale() is False

    def test_is_stale_when_old(self):
        """Test that old lock is considered stale."""
        lock = JobLock.objects.first()
        lock.acquired_at = timezone.now() - timedelta(hours=4)
        assert lock.is_stale() is True

    def test_missing_lock_record_auto_recovery(self):
        """Test that missing lock record is auto-created."""
        JobLock.objects.all().delete()

        assert acquire_lock(JobLock.LockTypes.CLUSTERING) is True

        locks = list(JobLock.objects.all())
        assert len(locks) == 1
        assert locks[0].lock_name == JobLock.LockTypes.CLUSTERING
        assert locks[0].acquired_at is not None

    def test_multiple_lock_records_raises_error(self):
        """Test that database prevents creating a duplicate lock row."""
        with transaction.atomic():
            with pytest.raises(IntegrityError):
                JobLock.objects.create(lock_name="", acquired_at=None, acquired_by="")

        assert acquire_lock(JobLock.LockTypes.CLUSTERING) is True

    def test_database_prevents_multiple_lock_records(self):
        """Test that database-level UNIQUE constraint prevents multiple lock records."""
        JobLock.objects.all().delete()

        JobLock.objects.create(lock_name="", acquired_at=None, acquired_by="")

        with transaction.atomic():
            with pytest.raises(IntegrityError):
                JobLock.objects.create(lock_name="", acquired_at=None, acquired_by="")

        lock_count = JobLock.objects.count()
        assert lock_count == 1, f"Expected 1 lock, got {lock_count}"

    def test_check_constraint_prevents_invalid_singleton_key(self):
        """Constraint prevents singleton_key from being anything other than 1."""
        JobLock.objects.all().delete()

        lock1 = JobLock.objects.create(
            singleton_key=1, lock_name="", acquired_at=None, acquired_by=""
        )
        assert lock1.singleton_key == 1

        with transaction.atomic():
            with pytest.raises(IntegrityError, match="singleton_key_must_be_one"):
                JobLock.objects.create(
                    singleton_key=2, lock_name="", acquired_at=None, acquired_by=""
                )

        with transaction.atomic():
            with pytest.raises(IntegrityError, match="singleton_key_must_be_one"):
                JobLock.objects.create(
                    singleton_key=3, lock_name="", acquired_at=None, acquired_by=""
                )

        assert JobLock.objects.count() == 1
