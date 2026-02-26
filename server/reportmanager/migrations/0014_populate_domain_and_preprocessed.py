from itertools import batched
from django.db import migrations
from urllib.parse import urlsplit
from reportmanager.utils import preprocess_text


def populate_domain_and_preprocessed(apps, schema_editor):
    """Populate domain and comments_preprocessed fields for existing records."""
    ReportEntry = apps.get_model('reportmanager', 'ReportEntry')

    batch_size = 500
    updated_count = 0

    entries = ReportEntry.objects.all()
    total = entries.count()

    for batch in batched(entries, batch_size):
        entries_to_update = []

        for entry in batch:
            try:
                parsed = urlsplit(entry.url)
                entry.domain = parsed.hostname or "unknown"
            except Exception:
                entry.domain = "unknown"

            text = entry.comments_translated or entry.comments
            entry.comments_preprocessed = preprocess_text(text)

            entries_to_update.append(entry)

        ReportEntry.objects.bulk_update(
            entries_to_update,
            ['domain', 'comments_preprocessed']
        )
        updated_count += len(entries_to_update)

        if updated_count % 5000 == 0:
            print(f"Updated {updated_count}/{total} records...")

    print(f"Completed: Updated {updated_count} records")


def reverse_populate(apps, schema_editor):
    """Reverse migration - clear the populated fields."""
    ReportEntry = apps.get_model('reportmanager', 'ReportEntry')
    ReportEntry.objects.all().update(domain=None, comments_preprocessed=None)


class Migration(migrations.Migration):

    dependencies = [
        ('reportmanager', '0013_reportentry_comments_preprocessed_reportentry_domain'),
    ]

    operations = [
        migrations.RunPython(populate_domain_and_preprocessed, reverse_populate),
    ]
