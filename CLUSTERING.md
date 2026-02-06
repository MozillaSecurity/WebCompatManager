# Clustering reports by similarity

## Overview

The clustering mechanism groups similar reports within each domain using unsupervised machine learning (SBERT embeddings and agglomerative clustering) and creates a bucket for each cluster. 

## One-time clustering of existing reports

This command clusters reports by similarity and creates buckets for existing reports and intended to be run once. 
Note that rerunning this command **will delete existing clusters and cluster-based buckets** and recreate them from scratch. 


```bash
# Cluster reports for a specific domain only
uv run -p 3.12 --extra=server server/manage.py cluster_reports --domain example.com

# Cluster all reports across all domains
uv run -p 3.12 --extra=server server/manage.py cluster_reports cluster_reports

```

The command performs the following steps:

1. Removes existing clusters and their associated buckets, if any exist.
2. Fetches reports from the database based on the following criteria:
   - Non-empty comments
   - ML validity score above 0.03 (reports that are invalid with probability 97% are skipped)

   Reports that don't meet these criteria are skipped from clustering and remain in the default domain-based bucket.

3. Reports are organized by domain and each domain is processed independently.
4. There are different strategies based on domain volume:

      **High-Volume Domains** (>20 reports per week):
      - Uses only the last 14 days of reports to focus on recent issues
      - Applies a stricter similarity threshold (0.30) to create more granular clusters

      **Normal-Volume Domains** (≤20 reports per week):
      - Uses all historical reports
      - Applies a more permissive threshold (0.38) so we can find patterns even with fewer reports

   The clustering process then:
   - Generates semantic embeddings for each report comment using SBERT
   - Groups similar embeddings using agglomerative clustering
   - Identifies a centroid (most representative report) for each cluster

5. Creates clusters based on the results of the clustering algorithm. Single-report clusters are discarded if their ML validity probability is below 0.60. These reports remain in the default domain-based buckets.

6. Clusters are saved to the database along with corresponding buckets. Each bucket receives a signature containing the domain and cluster ID for future report assignment.

## Clustering algorithm details

### Semantic Embeddings
The system uses SBERT (Sentence-BERT) to convert report text into semantic embeddings—vector representations that capture meaning of a report.
Once embeddings are created is uses agglomerative clustering, a hierarchical approach that:
1. Begins with each report as its own cluster
2. Iteratively merges the most similar clusters
3. Stops when all remaining cluster pairs exceed the distance threshold

### Threshold Selection
The distance threshold determines the maximum distance at which two reports will be grouped together. Lower thresholds produce smaller, more specific clusters (only very similar reports group together); higher thresholds create larger, more general clusters (moderately similar reports can group together).

The threshold varies based on domain volume:
- **High-volume domains** (0.30 threshold = 70% similarity): Stricter matching since sufficient data exists to form meaningful specific clusters
- **Normal-volume domains** (0.38 threshold = 62% similarity): More permissive matching to detect patterns despite limited number of reports

### Centroid Selection
Each cluster's centroid is the report whose embedding is closest to the cluster's mean embedding. This report serves as the most representative example of the cluster.
