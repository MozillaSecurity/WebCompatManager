# Generated by Django 4.2.13 on 2024-09-26 16:38

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = (("reportmanager", "0007_bucket_hide_until"),)

    operations = (
        migrations.AddField(
            model_name="bucket",
            name="reassign_in_progress",
            field=models.BooleanField(default=False),
        ),
    )
