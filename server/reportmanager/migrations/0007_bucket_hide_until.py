# Generated by Django 4.2.13 on 2024-09-25 02:36

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = (
        ("reportmanager", "0006_remove_bucket_snooze_until_bucketwatch_and_more"),
    )

    operations = (
        migrations.AddField(
            model_name="bucket",
            name="hide_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
    )
