<template>
  <div class="panel panel-default">
    <div class="panel-heading">
      <i class="bi bi-diagram-3"></i> Report Clustering
    </div>
    <div class="panel-body">
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
            <th>Buckets created</th>
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

export default {
  name: "Clustering",
  data() {
    return {
      jobs: [],
      loading: true,
      pollInterval: null,
    };
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
      } catch (err) {
        console.error("Failed to fetch clustering jobs:", err);
        this.loading = false;
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
