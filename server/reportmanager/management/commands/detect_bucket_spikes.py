from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction

from reportmanager.models import BucketSpike, ReportEntry, SpikeDetectionRun


class Command(BaseCommand):
    help = "Detect spikes using short and long window"

    def get_bucket_daily_data(self, start_date, end_date):
        reports = ReportEntry.objects.filter(
            reported_at__date__gte=start_date,
            reported_at__date__lte=end_date,
            bucket__isnull=False,
        ).values_list("bucket_id", "reported_at", "comments")

        bucket_daily_data = defaultdict(
            lambda: defaultdict(lambda: {"total": 0, "with_comments": 0})
        )

        for bucket_id, reported_at, comments in reports:
            day = reported_at.date()
            bucket_daily_data[bucket_id][day]["total"] += 1
            if comments and comments.strip():
                bucket_daily_data[bucket_id][day]["with_comments"] += 1

        return bucket_daily_data

    def determine_end_date(self):
        """Determines the end date for the detection run.

        Instead of using today's date return the date of the last bucketed
        report because reports are delayed by a day
        """
        last_bucketed_report = (
            ReportEntry.objects.filter(bucket__isnull=False)
            .order_by("-reported_at")
            .first()
        )

        if not last_bucketed_report:
            print("No bucketed reports found")
            return None

        print(f"Latest bucketed report: {last_bucketed_report.reported_at}")
        return last_bucketed_report.reported_at.date()

    def find_existing_run(self, date):
        return (
            SpikeDetectionRun.objects.filter(
                short_window_end=date,
            )
            .order_by("-short_window_end")
            .first()
        )

    def delete_existing_run(self, existing_run):
        old_run_id = existing_run.id
        spike_count = existing_run.spikes.count()
        existing_run.delete()

        print(f"Deleted existing run #{old_run_id} with {spike_count} spikes")

    def create_detection_run(self, threshold, short_window_start, short_window_end):
        detection_run = SpikeDetectionRun.objects.create(
            threshold=threshold,
            short_window_start=short_window_start,
            short_window_end=short_window_end,
        )
        print(f"Created detection run #{detection_run.id}")
        return detection_run

    def process_bucket(
        self,
        bucket_id,
        daily_counts,
        short_window_start,
        short_window_days,
        long_window_days,
        threshold,
        min_reports,
        detection_run,
    ):
        short_window_count = sum(
            counts["total"]
            for date, counts in daily_counts.items()
            if date >= short_window_start
        )

        short_window_count_with_comments = sum(
            counts["with_comments"]
            for date, counts in daily_counts.items()
            if date >= short_window_start
        )

        long_window_count = sum(counts["total"] for counts in daily_counts.values())

        if long_window_count < min_reports:
            return 0

        short_average = short_window_count / short_window_days
        long_average = long_window_count / long_window_days

        if long_average == 0:
            return 0

        ratio = short_average / long_average

        if ratio < threshold:
            return 0

        BucketSpike.objects.create(
            detection_run=detection_run,
            bucket_id=bucket_id,
            short_count=short_window_count,
            short_count_with_comments=short_window_count_with_comments,
            short_average=short_average,
            long_average=long_average,
            ratio=round(ratio, 3),
        )

        return 1

    def handle(self, *args, **options):
        short_window = settings.SPIKES_SHORT_WINDOW
        long_window = settings.SPIKES_LONG_WINDOW
        threshold = settings.SPIKES_RATIO_THRESHOLD
        min_reports = settings.SPIKES_MIN_REPORTS

        end_date = self.determine_end_date()

        if not end_date:
            return

        long_window_start = end_date - timedelta(days=long_window - 1)
        short_window_start = end_date - timedelta(days=short_window - 1)

        print(f"Long window: {long_window_start} to {end_date} ({long_window} days)")
        print(f"Short window: {short_window_start} to {end_date} ({short_window} days)")

        bucket_daily_data = self.get_bucket_daily_data(long_window_start, end_date)
        existing_run = self.find_existing_run(end_date)

        with transaction.atomic():
            if existing_run:
                self.delete_existing_run(existing_run)

            detection_run = self.create_detection_run(
                threshold=threshold,
                short_window_start=short_window_start,
                short_window_end=end_date,
            )

            buckets_with_spikes = 0

            for bucket_id, daily_counts in bucket_daily_data.items():
                spikes_count = self.process_bucket(
                    bucket_id=bucket_id,
                    daily_counts=daily_counts,
                    short_window_start=short_window_start,
                    short_window_days=short_window,
                    long_window_days=long_window,
                    threshold=threshold,
                    min_reports=min_reports,
                    detection_run=detection_run,
                )

                if spikes_count > 0:
                    buckets_with_spikes += 1

            print(
                f"\n Detection run #{detection_run.id} completed:\n"
                f"  {buckets_with_spikes} buckets with spikes\n"
                f"  Window: {detection_run.short_window_start} to {detection_run.short_window_end}\n"
            )
