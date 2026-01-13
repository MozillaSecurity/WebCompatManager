import logging

from django.conf import settings
from django.core.management import BaseCommand, CommandError

from reportmanager.models import Bug, BugProvider

LOG = logging.getLogger("fm.reportmanager.bug_update_status")


class Command(BaseCommand):
    help = "Check the status of all bugs we have"

    def handle(self, *args, **options):
        if args:
            raise CommandError("Command doesn't accept any arguments")

        providers = BugProvider.objects.all()
        for provider in providers:
            provider_instance = provider.get_instance()
            provider_bugs = Bug.objects.filter(external_type=provider)
            bug_ids = list(provider_bugs.values_list("external_id", flat=True))

            if not bug_ids:
                continue

            username = getattr(settings, "BUGZILLA_USERNAME", None)
            password = getattr(settings, "BUGZILLA_PASSWORD", None)

            bug_status = provider_instance.get_bug_status(bug_ids, username, password)

            if not bug_status:
                raise RuntimeError("Error getting bug status from bug provider.")

            # Map to memorize which bugs we have duped to others
            bug_dup_map = {}

            for bug_id in bug_status:
                # It is possible that two buckets are linked to one bug which has been
                # marked as a duplicate of another. Once the first bug has been
                # processed, we don't need to process any more bugs with the same bug id
                if bug_id in bug_dup_map:
                    continue

                # Due to how duplicating bugs works, we can end up having multiple bug
                # objects with the same external bug id. Make sure we consider all of
                # them.
                bugs = provider_bugs.filter(external_id=bug_id)
                for bug in bugs:
                    if bug_status[bug_id] is None and bug.closed is not None:
                        bug.closed = None
                        bug.save()
                    elif isinstance(bug_status[bug_id], str):
                        # The bug has been marked as a duplicate, so we change the
                        # external_id to match the duped bug. If that bug is also
                        # closed, then it will be picked up the next time this command
                        # runs.
                        LOG.info(
                            "setting bug %s dupe to %s",
                            bug.external_id,
                            bug_status[bug_id],
                        )
                        bug_dup_map[bug.external_id] = bug_status[bug_id]
                        bug.external_id = bug_status[bug_id]
                        bug.closed = None
                        bug.save()
                    elif bug.closed is None:
                        LOG.info(
                            "setting bug %s closed=%s",
                            bug.external_id,
                            bug_status[bug_id],
                        )
                        bug.closed = bug_status[bug_id]
                        bug.save()
