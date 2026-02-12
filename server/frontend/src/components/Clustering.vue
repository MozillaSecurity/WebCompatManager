<template>
  <div class="panel panel-default">
    <div class="panel-heading">
      <i class="bi bi-diagram-3"></i> Report Clustering
    </div>
    <div class="panel-body">
      <h4>Cluster Similar Reports</h4>
      <p>
        This tool analyzes reports and groups similar ones into clusters,
        creating buckets automatically based on similarity.
      </p>

      <hr />
      <h5>What happens when you run clustering?</h5>
      <ul>
        <li>Existing clusters and cluster-based buckets will be deleted</li>
        <li>Reports are analyzed for similarity using ML</li>
        <li>Similar reports are grouped into clusters</li>
        <li>
          New buckets are created for each cluster with description format:
          "domain [Cluster cluster_id]"
        </li>
        <li>Reports are automatically assigned to their cluster buckets</li>
        <li>
          This operation runs in the background and may take several minutes
        </li>
      </ul>

      <div v-if="clusteringInProgress" class="alert alert-info" role="alert">
        <i class="bi bi-hourglass-split"></i> Clustering is currently in
        progress. Please wait until it completes before starting a new run.
      </div>

      <div v-if="!clusteringInProgress" class="form-group">
        <label for="domain-input">Domain (optional):</label>
        <input
          id="domain-input"
          v-model="domain"
          type="text"
          class="form-control"
          placeholder="e.g., example.com (leave empty to cluster all domains)"
          style="max-width: 400px"
        />
        <small class="form-text text-muted">
          Leave empty to cluster reports across all domains, or specify a domain
          to cluster only reports from that domain.
        </small>
      </div>

      <button
        v-if="!clusteringInProgress"
        type="button"
        class="btn btn-primary"
        :disabled="!canEdit"
        @click="triggerClustering"
      >
        <i class="bi bi-play-circle"></i> Run Clustering
      </button>

      <div v-if="!canEdit" class="alert alert-warning mt-3" role="alert">
        You don't have permission to run clustering.
      </div>

      <div v-if="successMessage" class="alert alert-success mt-3" role="alert">
        {{ successMessage }}
      </div>

      <div v-if="errorMessage" class="alert alert-danger mt-3" role="alert">
        {{ errorMessage }}
      </div>

      <hr />

      <h4>History</h4>
      <div v-if="loading" class="text-center">
        <i class="bi bi-hourglass-split"></i> Loading...
      </div>

      <div v-else-if="jobs.length === 0" class="alert alert-info" role="alert">
        No clustering jobs have been run yet.
      </div>

      <table v-else class="table table-striped">
        <thead>
          <tr>
            <th>Type</th>
            <th>Started At</th>
            <th>Completed At</th>
            <th>Status</th>
            <th>Domain</th>
            <th>Cluster-based buckets created</th>
            <th>Error</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="job in jobs" :key="job.id">
            <td>
              <span v-if="job.job_type === 'full'" class="label label-primary"
                >Full</span
              >
              <span v-else class="label label-default">Incremental</span>
            </td>
            <td>{{ formatDate(job.started_at) }}</td>
            <td>
              <span v-if="job.completed_at">{{
                formatDate(job.completed_at)
              }}</span>
              <span v-else class="label label-info">In Progress</span>
            </td>
            <td>
              <span v-if="!job.completed_at" class="label label-info"
                >Running</span
              >
              <span v-else-if="job.is_ok" class="label label-success"
                >Success</span
              >
              <span v-else class="label label-danger">Failed</span>
            </td>
            <td>{{ job.domain || "All domains" }}</td>
            <td>{{ job.buckets_created }}</td>
            <td>
              <span v-if="job.error_message" class="text-danger">{{
                job.error_message
              }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import * as api from "../api.js";
import { errorParser } from "../helpers.js";

export default {
  name: "Clustering",
  props: {
    canEdit: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      domain: "",
      successMessage: "",
      errorMessage: "",
      jobs: [],
      loading: true,
      pollInterval: null,
      submitting: false,
    };
  },
  computed: {
    clusteringInProgress() {
      return (
        this.submitting ||
        (this.jobs.length > 0 && this.jobs[0].completed_at === null)
      );
    },
  },
  mounted() {
    this.fetchJobs();
    this.pollInterval = setInterval(() => {
      this.fetchJobs();
    }, 10000);
  },
  beforeUnmount() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
    }
  },
  methods: {
    async fetchJobs() {
      try {
        const data = await api.listClusteringJobs({ limit: 10 });
        this.jobs = data.results || data;
        this.loading = false;

        // Clear success message once the job completes
        if (this.successMessage && !this.clusteringInProgress) {
          this.successMessage = "";
        }
      } catch (err) {
        console.error("Failed to fetch clustering jobs:", err);
        this.loading = false;
      }
    },
    async triggerClustering() {
      if (!this.canEdit || this.clusteringInProgress) {
        return;
      }

      this.successMessage = "";
      this.errorMessage = "";
      this.submitting = true;

      try {
        const domainParam = this.domain.trim() || null;
        const response = await api.clusterReports(domainParam);

        this.successMessage =
          response.message || "Clustering task started successfully!";
        this.successMessage += " The process is running in the background.";

        // Clear domain input and refresh jobs
        this.domain = "";
        await this.fetchJobs();
      } catch (err) {
        console.error("Clustering error:", err);
        this.errorMessage =
          "Failed to start clustering: " +
          (errorParser(err) || "Unknown error occurred");
      } finally {
        this.submitting = false;
      }
    },
    formatDate(dateString) {
      if (!dateString) return "";
      const date = new Date(dateString);
      return date.toLocaleString();
    },
  },
};
</script>

<style scoped>
.mt-3 {
  margin-top: 1rem;
}
</style>
