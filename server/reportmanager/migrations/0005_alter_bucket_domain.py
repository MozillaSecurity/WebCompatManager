# Generated by Django 4.2.13 on 2024-09-18 21:45

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = (("reportmanager", "0004_buckethit_unique_buckethits"),)

    operations = (
        migrations.AlterField(
            model_name="bucket",
            name="domain",
            field=models.CharField(max_length=255, null=True),
        ),
    )