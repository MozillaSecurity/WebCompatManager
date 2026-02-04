"""Tests for clustering functionality."""

import json
from datetime import timedelta
from unittest.mock import Mock, patch

import numpy as np
import pytest
from django.utils import timezone

from reportmanager.clustering.ClusterBucketManager import (
    ClusterBucketManager,
    ClusterGroup,
    ClusterReport,
)
from reportmanager.clustering.SBERTClusterer import SBERTClusterer


@pytest.fixture
def mock_clusterer():
    """Create a mock SBERTClusterer for testing."""
    clusterer = Mock(spec=SBERTClusterer)
    return clusterer


@pytest.fixture
def manager(mock_clusterer):
    """Create a ClusterBucketManager with a mock clusterer."""
    with patch(
        "reportmanager.clustering.ClusterBucketManager.SBERTClusterer",
        return_value=mock_clusterer,
    ):
        return ClusterBucketManager()


@pytest.fixture
def sample_reports():
    """Create sample ClusterReport objects for testing."""
    now = timezone.now()
    return [
        ClusterReport(
            id=1,
            ml_valid_probability=0.8,
            reported_at=now,
            url="https://example.com/page1",
            bucket_id=None,
            text="Page loading issue",
            domain="example.com",
        ),
        ClusterReport(
            id=2,
            ml_valid_probability=0.7,
            reported_at=now - timedelta(days=1),
            url="https://example.com/page2",
            bucket_id=None,
            text="Page not loading correctly",
            domain="example.com",
        ),
        ClusterReport(
            id=3,
            ml_valid_probability=0.9,
            reported_at=now - timedelta(days=2),
            url="https://other.com/page",
            bucket_id=None,
            text="Different issue",
            domain="other.com",
        ),
    ]


class TestClusterBucketManager:
    """Tests for ClusterBucketManager."""

    def test_ok_to_cluster(self):
        """Test ok_to_cluster for various scenarios."""
        assert ClusterBucketManager.ok_to_cluster("Some text", 0.05) is True
        assert ClusterBucketManager.ok_to_cluster("Some text", 0.5) is True
        assert ClusterBucketManager.ok_to_cluster("", 0.5) is False
        assert ClusterBucketManager.ok_to_cluster("   ", 0.5) is False
        assert ClusterBucketManager.ok_to_cluster("Some text", 0.03) is False

    def test_group_reports_by_domain(self, manager, sample_reports):
        """Test grouping reports by domain."""
        reports_by_domain = manager.group_reports_by_domain(sample_reports)

        assert "example.com" in reports_by_domain
        assert "other.com" in reports_by_domain
        assert len(reports_by_domain["example.com"]) == 2
        assert len(reports_by_domain["other.com"]) == 1

    def test_group_reports_by_domain_filters_domains(self, manager, sample_reports):
        """Test grouping reports with domain filter."""
        reports_by_domain = manager.group_reports_by_domain(
            sample_reports, domains=["example.com"]
        )

        assert "example.com" in reports_by_domain
        assert "other.com" not in reports_by_domain

    def test_group_reports_by_domain_skips_not_ok_to_cluster(self, manager):
        """Test grouping skips reports that are not ok to cluster."""
        reports = [
            ClusterReport(
                id=1,
                ml_valid_probability=0.8,
                reported_at=timezone.now(),
                url="https://example.com",
                bucket_id=None,
                text="Valid text",
                domain="example.com",
            ),
            ClusterReport(
                id=2,
                ml_valid_probability=0.02,
                reported_at=timezone.now(),
                url="https://example.com",
                bucket_id=None,
                text="",
                domain="example.com",
            ),
        ]

        reports_by_domain = manager.group_reports_by_domain(reports)
        assert len(reports_by_domain["example.com"]) == 1

    def test_is_high_volume_domain_with_high_volume(self, manager):
        """Test detecting high-volume domains."""
        now = timezone.now()
        # Create 30 reports over 7 days = 30 reports/week (> 20 threshold)
        reports = [
            ClusterReport(
                id=i,
                ml_valid_probability=0.8,
                reported_at=now - timedelta(days=i % 7),
                url="https://example.com",
                bucket_id=None,
                text=f"Report {i}",
                domain="example.com",
            )
            for i in range(30)
        ]

        assert manager.is_high_volume_domain(reports) is True

    def test_is_high_volume_domain_with_normal_volume(self, manager):
        """Test detecting normal-volume domains."""
        now = timezone.now()
        # Create 10 reports over 7 days = 10 reports/week (< 20 threshold)
        reports = [
            ClusterReport(
                id=i,
                ml_valid_probability=0.8,
                reported_at=now - timedelta(days=i % 7),
                url="https://example.com",
                bucket_id=None,
                text=f"Report {i}",
                domain="example.com",
            )
            for i in range(10)
        ]

        assert manager.is_high_volume_domain(reports) is False

    def test_filter_recent_reports(self, manager):
        """Test filtering reports by date."""
        now = timezone.now()
        reports = [
            ClusterReport(
                id=1,
                ml_valid_probability=0.8,
                reported_at=now - timedelta(days=5),
                url="https://example.com",
                bucket_id=None,
                text="Recent",
                domain="example.com",
            ),
            ClusterReport(
                id=2,
                ml_valid_probability=0.8,
                reported_at=now - timedelta(days=20),
                url="https://example.com",
                bucket_id=None,
                text="Old",
                domain="example.com",
            ),
        ]

        recent = manager.filter_recent_reports(reports, days=14)
        assert len(recent) == 1
        assert recent[0].id == 1

    def test_group_reports_by_label(self, manager, sample_reports):
        """Test grouping reports by cluster labels."""
        labels = np.array([0, 0, 1])
        embeddings = np.array([[0.1, 0.2], [0.15, 0.25], [0.9, 0.8]])

        cluster_groups = manager.group_reports_by_label(
            sample_reports, labels, embeddings
        )

        assert len(cluster_groups) == 2
        groups_by_size = sorted(
            cluster_groups, key=lambda g: len(g.reports), reverse=True
        )
        assert len(groups_by_size[0].reports) == 2
        assert len(groups_by_size[0].embeddings) == 2
        assert len(groups_by_size[1].reports) == 1

    def test_group_reports_by_label_length_mismatch_reports_labels(self, manager):
        """Test that length mismatch between reports and labels raises error."""
        reports = [
            ClusterReport(
                id=1,
                ml_valid_probability=0.8,
                reported_at=timezone.now(),
                url="https://example.com",
                bucket_id=None,
                text="Report 1",
                domain="example.com",
            ),
            ClusterReport(
                id=2,
                ml_valid_probability=0.8,
                reported_at=timezone.now(),
                url="https://example.com",
                bucket_id=None,
                text="Report 2",
                domain="example.com",
            ),
        ]
        labels = np.array([0, 0, 1])  # 3 labels, but only 2 reports
        embeddings = np.array([[0.1, 0.2], [0.15, 0.25]])

        with pytest.raises(AssertionError, match="Length mismatch"):
            manager.group_reports_by_label(reports, labels, embeddings)

    def test_build_clusters_skips_low_probability_single_reports(
        self, manager, mock_clusterer
    ):
        """Test that single-report clusters with low probability are skipped."""
        mock_clusterer.find_centroid_index.return_value = 0

        cluster_groups = [
            ClusterGroup(
                reports=[
                    ClusterReport(
                        id=1,
                        ml_valid_probability=0.49,  # Below threshold of 0.60
                        reported_at=timezone.now(),
                        url="https://example.com",
                        bucket_id=None,
                        text="Low quality",
                        domain="example.com",
                    )
                ],
                embeddings=[[0.1, 0.2]],
            )
        ]

        clusters = manager.build_clusters(cluster_groups, "example.com")
        assert len(clusters) == 0

    def test_build_clusters_keeps_high_probability_single_reports(
        self, manager, mock_clusterer
    ):
        """Test that single-report clusters with high probability are kept."""
        mock_clusterer.find_centroid_index.return_value = 0

        cluster_groups = [
            ClusterGroup(
                reports=[
                    ClusterReport(
                        id=1,
                        ml_valid_probability=0.9,  # Above threshold of 0.60
                        reported_at=timezone.now(),
                        url="https://example.com",
                        bucket_id=None,
                        text="High quality",
                        domain="example.com",
                    )
                ],
                embeddings=[[0.1, 0.2]],
            )
        ]

        clusters = manager.build_clusters(cluster_groups, "example.com")
        assert len(clusters) == 1
        assert clusters[0].centroid_id == 1

    def test_build_clusters_keeps_multi_report_clusters(self, manager, mock_clusterer):
        """Test that multi-report clusters are kept regardless of probability."""
        mock_clusterer.find_centroid_index.return_value = 1

        cluster_groups = [
            ClusterGroup(
                reports=[
                    ClusterReport(
                        id=1,
                        ml_valid_probability=0.59,
                        reported_at=timezone.now(),
                        url="https://example.com",
                        bucket_id=None,
                        text="Report 1",
                        domain="example.com",
                    ),
                    ClusterReport(
                        id=2,
                        ml_valid_probability=0.45,
                        reported_at=timezone.now(),
                        url="https://example.com",
                        bucket_id=None,
                        text="Report 2",
                        domain="example.com",
                    ),
                ],
                embeddings=[[0.1, 0.2], [0.15, 0.25]],
            )
        ]

        clusters = manager.build_clusters(cluster_groups, "example.com")
        assert len(clusters) == 1
        assert clusters[0].centroid_id == 2

    def test_build_cluster_bucket_signature(self, manager):
        """Test building bucket signature for a cluster."""
        signature_str = manager.build_cluster_bucket_signature("example.com", 123)
        signature = json.loads(signature_str)

        assert "symptoms" in signature
        assert len(signature["symptoms"]) == 2
        assert signature["symptoms"][0]["type"] == "url"
        assert signature["symptoms"][0]["part"] == "hostname"
        assert signature["symptoms"][0]["value"] == "example.com"
        assert signature["symptoms"][1]["type"] == "cluster_id"
        assert signature["symptoms"][1]["value"] == "123"
