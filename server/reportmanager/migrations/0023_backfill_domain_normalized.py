from django.db import migrations
from reportmanager.utils import normalize_domain

BATCH_SIZE = 1000


def backfill_domain_normalized(apps, schema_editor):
    Bucket = apps.get_model("reportmanager", "Bucket")
    qs = Bucket.objects.exclude(domain__isnull=True).only(
        "id", "domain", "domain_normalized"
    )

    batch = []
    for bucket in qs.iterator(chunk_size=BATCH_SIZE):
        new_value = normalize_domain(bucket.domain)
        if new_value != bucket.domain_normalized:
            bucket.domain_normalized = new_value
            batch.append(bucket)
            if len(batch) >= BATCH_SIZE:
                Bucket.objects.bulk_update(batch, ["domain_normalized"])
                batch = []
    if batch:
        Bucket.objects.bulk_update(batch, ["domain_normalized"])


def reverse_clear(apps, schema_editor):
    Bucket = apps.get_model("reportmanager", "Bucket")
    Bucket.objects.update(domain_normalized=None)


class Migration(migrations.Migration):

    dependencies = [
        ("reportmanager", "0022_bucket_domain_normalized_label_bucketlabel"),
    ]

    operations = [
        migrations.RunPython(backfill_domain_normalized, reverse_clear),
    ]