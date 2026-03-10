# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os
import socket
from collections.abc import Generator
from contextlib import contextmanager

from django.db import transaction
from django.utils import timezone

from reportmanager.models import JobLock

LOG = logging.getLogger("reportmanager.locking")


class JobLockError(Exception):
    pass


def get_process_identifier() -> str:
    """Get a string identifying this process for debugging."""
    hostname = socket.gethostname()
    pid = os.getpid()
    return f"{hostname}:{pid}"


def acquire_lock(lock_name: str) -> bool:
    """Acquire a lock by updating the existing JobLock record."""

    with transaction.atomic():
        lock = JobLock.objects.select_for_update().first()

        if lock is None:
            raise JobLockError("No lock record exists in database.")

        acquired_by = get_process_identifier()

        if lock.is_locked:
            if lock.is_stale():
                LOG.warning(
                    f"Releasing stale lock '{lock.lock_name}' "
                    f"(held since {lock.acquired_at} by {lock.acquired_by})"
                )
                # Release the stale lock and acquire the new one
                lock.acquire(lock_name, acquired_by)
            else:
                raise JobLockError(
                    f"Cannot acquire lock '{lock_name}': "
                    f"another operation '{lock.lock_name}' is in progress "
                    f"(held by {lock.acquired_by} since {lock.acquired_at})"
                )
        else:
            lock.acquire(lock_name, acquired_by)

        LOG.info(f"Acquired lock '{lock_name}' (by {acquired_by})")
        return True


def release_lock(lock_name: str) -> None:
    """Release a previously acquired lock."""
    with transaction.atomic():
        lock = JobLock.objects.select_for_update().first()

        if lock is None:
            LOG.warning(
                f"Attempted to release lock '{lock_name}' but no lock record exists"
            )
            return

        if not lock.is_locked:
            LOG.warning(f"Attempted to release lock '{lock_name}' but it's not locked")
            return

        if lock.lock_name != lock_name:
            LOG.warning(
                f"Attempted to release lock '{lock_name}' "
                f"but the current lock is '{lock.lock_name}'"
            )
            return

        acquired_by = lock.acquired_by
        acquired_at = lock.acquired_at
        duration = timezone.now() - acquired_at if acquired_at else None

        lock.release()

        duration_str = (
            f"{duration.total_seconds():.1f}s" if duration else "unknown duration"
        )
        LOG.info(
            f"Released lock '{lock_name}' (held for {duration_str} by {acquired_by})"
        )


@contextmanager
def acquire_job_lock(lock_name: str) -> Generator[None, None, None]:
    """Context manager for acquiring and automatically releasing a job lock.

    To run:
        try:
            with acquire_job_lock(JobLock.LockTypes.CLUSTERING):
                # Do clustering work
                ...
        except JobLockError as e:
            LOG.warning(f"Could not acquire lock: {e}")
            return
    """
    acquire_lock(lock_name)
    try:
        yield
    finally:
        release_lock(lock_name)
