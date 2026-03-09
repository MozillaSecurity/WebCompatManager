# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os
import socket
from collections.abc import Generator
from contextlib import contextmanager

from django.db import IntegrityError
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
    """Acquire a lock by creating a JobLock record.

    (only one lock can exist in the database at any time, regardless of name)

    """

    if lock_name not in JobLock.LOCK_TYPES:
        raise ValueError(
            f"Invalid lock type '{lock_name}'. Valid types: {JobLock.LOCK_TYPES}"
        )

    acquired_by = get_process_identifier()
    existing_lock = JobLock.objects.first()

    if existing_lock:
        if existing_lock.is_stale():
            LOG.warning(
                f"Releasing stale lock '{existing_lock.lock_name}' "
                f"(held since {existing_lock.acquired_at}"
                f"by {existing_lock.acquired_by})"
            )
            existing_lock.delete()
        else:
            raise JobLockError(
                f"Cannot acquire lock '{lock_name}': "
                f"another operation '{existing_lock.lock_name}' is in progress "
                f"(held by {existing_lock.acquired_by} "
                f"since {existing_lock.acquired_at})"
            )

    try:
        JobLock.objects.create(lock_name=lock_name, acquired_by=acquired_by)
        LOG.info(f"Acquired lock '{lock_name}' (by {acquired_by})")
        return True
    except IntegrityError:
        raise JobLockError(
            f"Cannot acquire lock '{lock_name}': another process acquired a lock"
        )


def release_lock(lock_name: str) -> None:
    """Release a previously acquired lock."""
    try:
        lock = JobLock.objects.get(lock_name=lock_name)
        acquired_by = lock.acquired_by
        acquired_at = lock.acquired_at
        lock.delete()

        duration = timezone.now() - acquired_at
        LOG.info(
            f"Released lock '{lock_name}' "
            f"(held for {duration.total_seconds():.1f}s by {acquired_by})"
        )

    except JobLock.DoesNotExist:
        LOG.warning(f"Attempted to release lock '{lock_name}' but it doesn't exist")


@contextmanager
def acquire_job_lock(lock_name: str) -> Generator[None, None, None]:
    """Context manager for acquiring and automatically releasing a job lock.

    To run:
        try:
            with acquire_job_lock(JobLock.CLUSTERING):
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
