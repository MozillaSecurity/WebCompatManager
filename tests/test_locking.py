from datetime import timedelta

import pytest
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
        """Test that multiple lock records detected"""
        JobLock.objects.create(lock_name="", acquired_at=None, acquired_by="")

        with pytest.raises(
            JobLockError, match="2 lock records exist, expected exactly 1"
        ):
            acquire_lock(JobLock.LockTypes.CLUSTERING)

    def test_multiple_lock_records_on_release_raises_error(self):
        """Test that multiple lock records detected during release."""
        acquire_lock(JobLock.LockTypes.CLUSTERING)

        JobLock.objects.create(lock_name="", acquired_at=None, acquired_by="")

        with pytest.raises(
            JobLockError, match="2 lock records exist, expected exactly 1"
        ):
            release_lock(JobLock.LockTypes.CLUSTERING)
