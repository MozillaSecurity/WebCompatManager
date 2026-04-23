"""This script creates tests/e2e/fixtures/fixtures.json with test data.

Rerun this script if any new fields have to be added to fixture json file
when Django models change (Bucket, ReportEntry, Cluster, etc.)

Usage:
    uv run --extra=server python tests/e2e/scripts/generate_e2e_fixtures.py
"""
# ruff: noqa: E501, PERF401

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

BUCKETS_CONFIG = [
    {
        "id": 131189,
        "domain": "www.joyn.de",
        "description": "www.joyn.de [Cluster 70854]",
        "cluster_id": 70854,
        "priority": 0,
        "signature": '{"symptoms": [{"type": "url", "part": "hostname", "value": "www.joyn.de"}]}',
        "comments": [
            {
                "comments": "Der Videoplayer ladt nicht. Nur schwarzer Bildschirm.",
                "comments_translated": "The video player doesn't load. Only black screen.",
                "comments_original_language": "de",
                "breakage_category": "load",
                "ml_valid_probability": 0.842287540435791,
            },
            {
                "comments": "Video startet nicht, Player bleibt schwarz",
                "comments_translated": "Video doesn't start, player stays black",
                "comments_original_language": "de",
                "breakage_category": "media",
                "ml_valid_probability": 0.9333918690681458,
            },
            {
                "comments": "Schwarzer Screen beim Abspielen",
                "comments_translated": "Black screen when playing",
                "comments_original_language": "de",
                "breakage_category": "load",
                "ml_valid_probability": 0.6257511377334595,
            },
            {
                "comments": "Video wird auf Android nicht abgespielt",
                "comments_translated": "Video doesn't play on Android",
                "comments_original_language": "de",
                "breakage_category": "media",
                "ml_valid_probability": 0.8234567,
            },
        ],
    },
    {
        "id": 133162,
        "domain": "www.filae.com",
        "description": "www.filae.com [Cluster 72827]",
        "cluster_id": 72827,
        "priority": 0,
        "signature": '{"symptoms": [{"type": "url", "part": "hostname", "value": "www.filae.com"}]}',
        "comments": [
            {
                "comments": "La page ne charge pas correctement. Je dois actualiser plusieurs fois.",
                "comments_translated": "The page doesn't load correctly. I have to refresh multiple times.",
                "comments_original_language": "fr",
                "breakage_category": "content",
                "ml_valid_probability": 0.9146597981452942,
            },
            {
                "comments": "Impossible d'ouvrir les images, page blanche affichée",
                "comments_translated": "Unable to open images, blank page displayed",
                "comments_original_language": "fr",
                "breakage_category": "other",
                "ml_valid_probability": 0.7248315811157227,
            },
            {
                "comments": "En cliquant sur un lien, la page reste blanche",
                "comments_translated": "When clicking a link, the page stays blank",
                "comments_original_language": "fr",
                "breakage_category": "load",
                "ml_valid_probability": 0.9729971885681152,
            },
        ],
    },
    {
        "id": 132454,
        "domain": "www.vicroads.vic.gov.au",
        "description": "www.vicroads.vic.gov.au [Cluster 72119]",
        "cluster_id": 72119,
        "priority": 0,
        "signature": '{"symptoms": [{"type": "url", "part": "hostname", "value": "www.vicroads.vic.gov.au"}]}',
        "comments": [
            {
                "comments": "Site loads but clicking links does nothing",
                "comments_translated": "Site loads but clicking links does nothing",
                "comments_original_language": "en",
                "breakage_category": "load",
                "ml_valid_probability": 0.9730769395828247,
            },
            {
                "comments": "Cannot navigate the site, links are unresponsive",
                "comments_translated": "Cannot navigate the site, links are unresponsive",
                "comments_original_language": "en",
                "breakage_category": "load",
                "ml_valid_probability": 0.9550638198852539,
            },
            {
                "comments": "Page reloads when selecting any option, can't get past home page",
                "comments_translated": "Page reloads when selecting any option, can't get past home page",
                "comments_original_language": "en",
                "breakage_category": "other",
                "ml_valid_probability": 0.5003429651260376,
            },
        ],
    },
    {
        "id": 132456,
        "domain": "www.vicroads.vic.gov.au",
        "description": "www.vicroads.vic.gov.au [Cluster 72121]",
        "cluster_id": 72121,
        "priority": 0,
        "signature": '{"symptoms": [{"type": "url", "part": "hostname", "value": "www.vicroads.vic.gov.au"}]}',
        "comments": [
            {
                "comments": "Login button redirects back to main page",
                "comments_translated": "Login button redirects back to main page",
                "comments_original_language": "en",
                "breakage_category": "account",
                "ml_valid_probability": 0.3770124912261963,
            },
            {
                "comments": "Can't access login page, works fine in Chrome",
                "comments_translated": "Can't access login page, works fine in Chrome",
                "comments_original_language": "en",
                "breakage_category": "notsupported",
                "ml_valid_probability": 0.9809913039207458,
            },
        ],
    },
    {
        "id": 152242,
        "domain": "www.vicroads.vic.gov.au",
        "description": "domain is www.vicroads.vic.gov.au",
        "cluster_id": None,
        "priority": 0,
        "signature": '{"symptoms": [{"type": "url", "part": "hostname", "value": "www.vicroads.vic.gov.au"}]}',
        "comments": [
            {
                "comments": "",
                "comments_translated": "",
                "comments_original_language": None,
                "breakage_category": "account",
                "ml_valid_probability": None,
            },
            {
                "comments": "",
                "comments_translated": "",
                "comments_original_language": None,
                "breakage_category": "checkout",
                "ml_valid_probability": None,
            },
            {
                "comments": "",
                "comments_translated": "",
                "comments_original_language": None,
                "breakage_category": "account",
                "ml_valid_probability": None,
            },
            {
                "comments": "",
                "comments_translated": "",
                "comments_original_language": None,
                "breakage_category": "account",
                "ml_valid_probability": None,
            },
        ],
    },
    {
        "id": 6281,
        "domain": "www.filae.com",
        "description": "domain is www.filae.com",
        "cluster_id": None,
        "priority": 0,
        "signature": '{"symptoms": [{"type": "url", "part": "hostname", "value": "www.filae.com"}]}',
        "comments": [
            {
                "comments": "",
                "comments_translated": "",
                "comments_original_language": None,
                "breakage_category": "load",
                "ml_valid_probability": None,
            },
        ],
    },
    {
        "id": 1602,
        "domain": "www.joyn.de",
        "description": "domain is www.joyn.de",
        "cluster_id": None,
        "priority": 0,
        "signature": '{"symptoms": [{"type": "url", "part": "hostname", "value": "www.joyn.de"}]}',
        "comments": [
            {
                "comments": "",
                "comments_translated": "",
                "comments_original_language": None,
                "breakage_category": "media",
                "ml_valid_probability": None,
            },
            {
                "comments": "",
                "comments_translated": "",
                "comments_original_language": None,
                "breakage_category": "media",
                "ml_valid_probability": None,
            },
        ],
    },
]

# Supporting data
OS_DATA = [
    {"id": 1, "name": "Windows"},
    {"id": 2, "name": "Mac"},
    {"id": 3, "name": "Linux"},
    {"id": 4, "name": "Android"},
]

APP_DATA = [
    {"id": 1, "name": "Firefox", "version": "148.0", "channel": "release"},
    {"id": 2, "name": "Firefox", "version": "147.0.3", "channel": "release"},
    {"id": 3, "name": "Firefox", "version": "134.0", "channel": "release"},
]

BREAKAGE_CATEGORIES = [
    {"id": 1, "value": "load"},
    {"id": 2, "value": "media"},
    {"id": 3, "value": "content"},
    {"id": 4, "value": "other"},
    {"id": 5, "value": "account"},
    {"id": 6, "value": "notsupported"},
    {"id": 7, "value": "checkout"},
]


def generate_fixtures():
    fixture = []

    for os_data in OS_DATA:
        fixture.append(
            {
                "model": "reportmanager.os",
                "pk": os_data["id"],
                "fields": {"name": os_data["name"]},
            }
        )

    for cat in BREAKAGE_CATEGORIES:
        fixture.append(
            {
                "model": "reportmanager.breakagecategory",
                "pk": cat["id"],
                "fields": {"value": cat["value"]},
            }
        )

    for app in APP_DATA:
        fixture.append(
            {
                "model": "reportmanager.app",
                "pk": app["id"],
                "fields": {
                    "name": app["name"],
                    "version": app["version"],
                    "channel": app["channel"],
                },
            }
        )

    # Buckets (will be updated with cluster references later)
    for bucket_config in BUCKETS_CONFIG:
        fixture.append(
            {
                "model": "reportmanager.bucket",
                "pk": bucket_config["id"],
                "fields": {
                    "bug": None,
                    "color": None,
                    "description": bucket_config["description"],
                    "domain": bucket_config["domain"],
                    "hide_until": None,
                    "priority": bucket_config["priority"],
                    "signature": bucket_config["signature"],
                    "reassign_in_progress": False,
                    "cluster": bucket_config["cluster_id"],
                },
            }
        )

    # Reports (need to create these before clusters since clusters reference centroids)
    report_id_counter = 1000  # Start from arbitrary ID
    cluster_to_centroid = {}  # Track centroid for each cluster

    date_offsets = [1, 3, 14, 30, 60]

    for bucket_config in BUCKETS_CONFIG:
        for i, comment_data in enumerate(bucket_config["comments"]):
            report_id = report_id_counter
            report_id_counter += 1

            # First report of a clustered bucket is the centroid
            if i == 0 and bucket_config["cluster_id"]:
                cluster_to_centroid[bucket_config["cluster_id"]] = report_id

            # Get breakage category ID
            breakage_category_id = next(
                (
                    cat["id"]
                    for cat in BREAKAGE_CATEGORIES
                    if cat["value"] == comment_data["breakage_category"]
                ),
                None,
            )

            comments = comment_data["comments"]
            comments_translated = comment_data["comments_translated"]
            comments_preprocessed = (
                comments_translated.lower() if comments_translated else ""
            )

            days_ago = date_offsets[i % len(date_offsets)]

            fixture.append(
                {
                    "model": "reportmanager.reportentry",
                    "pk": report_id,
                    "fields": {
                        "app": (i % len(APP_DATA))
                        + 1,  # Rotate through all app versions
                        "breakage_category": breakage_category_id,
                        "bucket": bucket_config["id"],
                        "comments": comments,
                        "comments_translated": comments_translated,
                        "comments_original_language": comment_data[
                            "comments_original_language"
                        ],
                        "comments_preprocessed": comments_preprocessed,
                        "details": {},
                        "domain": bucket_config["domain"],
                        "ml_valid_probability": comment_data["ml_valid_probability"],
                        "os": (i % len(OS_DATA)) + 1,  # Rotate through all OS
                        "reported_at": (
                            datetime.now(UTC) - timedelta(days=days_ago)
                        ).isoformat(),
                        "url": f"https://{bucket_config['domain']}/",
                        "uuid": str(uuid.uuid4()),
                        "cluster": bucket_config["cluster_id"],
                    },
                }
            )

    for bucket_config in BUCKETS_CONFIG:
        if bucket_config["cluster_id"]:
            cluster_id = bucket_config["cluster_id"]
            centroid_id = cluster_to_centroid[cluster_id]

            fixture.append(
                {
                    "model": "reportmanager.cluster",
                    "pk": cluster_id,
                    "fields": {
                        "domain": bucket_config["domain"],
                        "centroid": centroid_id,
                    },
                }
            )

    output_path = Path(__file__).parent.parent / "fixtures" / "fixtures.json"
    with open(output_path, "w") as f:
        json.dump(fixture, f, indent=2)

    print("\nBuckets generated:")
    for bucket in BUCKETS_CONFIG:
        report_count = len(bucket["comments"])
        bucket_type = "cluster-based" if bucket["cluster_id"] else "domain-only"
        print(
            f"  - {bucket['id']}: {bucket['domain']} ({bucket_type}): {report_count} reports"
        )


if __name__ == "__main__":
    generate_fixtures()
