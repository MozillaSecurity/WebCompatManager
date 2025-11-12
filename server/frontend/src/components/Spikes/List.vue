<template>
  <div class="panel panel-default">
    <div class="panel-heading"><i class="bi bi-activity"></i> Spikes</div>
    <div class="panel-body">
      <div class="parameters-section">
        <div class="row">
          <div class="col-md-3">
            <div class="form-group">
              <label
                >Min reports with non-empty comments:
                <strong>{{ minCommentsFilter }}</strong></label
              >
              <input
                type="range"
                class="form-control-range"
                v-model.number="minCommentsFilter"
                :min="0"
                :max="maxCommentsCount"
                step="1"
              />
            </div>
          </div>
          <div class="col-md-3">
            <div class="form-group">
              <label
                >Short Window (days): <strong>{{ shortWindow }}</strong></label
              >
              <input
                type="range"
                class="form-control-range"
                v-model.number="shortWindow"
                :min="1"
                :max="14"
                step="1"
                v-on:change="reloadSpikes"
              />
            </div>
          </div>
          <div class="col-md-3">
            <div class="form-group">
              <label
                >Long Window (days): <strong>{{ longWindow }}</strong></label
              >
              <input
                type="range"
                class="form-control-range"
                v-model.number="longWindow"
                :min="7"
                :max="90"
                step="1"
                v-on:change="reloadSpikes"
              />
            </div>
          </div>
        </div>
      </div>
      <div v-if="selectedPeriod">
        <p>
          {{ filteredSpikes.length }} spikes in window
          <strong>{{ shortWindowPeriod }}</strong>
        </p>
      </div>

      <div v-if="loading" class="text-center">
        <i class="bi bi-hourglass-split"></i> Loading...
      </div>
      <div v-else-if="filteredSpikes.length === 0" class="text-muted">
        No spikes detected with selected parameters.
      </div>
    </div>
    <div v-if="!loading && filteredSpikes.length > 0" class="table-responsive">
      <table class="table table-condensed table-bordered table-db">
        <thead>
          <tr>
            <th>Bucket</th>
            <th>Domain</th>
            <th class="text-right"># of reports</th>
            <th class="text-right"># of reports with comments</th>
            <th class="text-right">Short Avg</th>
            <th class="text-right">Long Avg</th>
            <th class="text-right">Ratio</th>
            <th>Comments</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="spike in filteredSpikes" :key="spike.id">
            <td>
              <a :href="spike.bucket_view_url">{{ spike.bucket_id }}</a>
            </td>
            <td>{{ spike.bucket_domain || "(no domain)" }}</td>
            <td class="text-right">{{ spike.short_count }}</td>
            <td class="text-right">{{ spike.short_count_with_comments }}</td>
            <td class="text-right">{{ spike.short_average.toFixed(2) }}</td>
            <td class="text-right">{{ spike.long_average.toFixed(2) }}</td>
            <td class="text-right">{{ spike.ratio.toFixed(2) }}</td>
            <td class="comments-cell">
              <ol
                v-if="spike.report_comments && spike.report_comments.length > 0"
              >
                <li
                  v-for="(comment, index) in spike.report_comments"
                  :key="index"
                >
                  {{ comment }}
                </li>
              </ol>
              <span v-else>—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import * as api from "../../api";

export default {
  name: "SpikesList",
  data() {
    return {
      loading: false,
      selectedPeriod: null,
      spikes: [],
      minCommentsFilter: 3,
      shortWindow: 2,
      longWindow: 60,
      threshold: 1.5,
      minTotalReports: 10,
    };
  },
  computed: {
    shortWindowPeriod() {
      if (!this.selectedPeriod) return "No period selected";
      return `${this.selectedPeriod.short_window_start} to ${this.selectedPeriod.short_window_end}`;
    },
    filteredSpikes() {
      return this.spikes.filter(
        (spike) => spike.short_count_with_comments >= this.minCommentsFilter,
      );
    },
    maxCommentsCount() {
      if (this.spikes.length === 0) return 0;
      return Math.max(...this.spikes.map((s) => s.short_count_with_comments));
    },
  },
  async mounted() {
    await this.fetchLatestRun();
  },
  methods: {
    async fetchLatestRun() {
      this.loading = true;
      try {
        const params = {
          short_window: this.shortWindow,
          long_window: this.longWindow,
          threshold: this.threshold,
          min_reports: this.minTotalReports,
        };

        const data = await api.getCurrentBucketSpikes(params);

        if (data) {
          this.selectedPeriod = {
            short_window_start: data.short_window_start,
            short_window_end: data.short_window_end,
          };
          this.spikes = data.spikes || [];
        }
      } catch (err) {
        console.error("Error fetching spikes:", err);
      }
      this.loading = false;
    },
    async reloadSpikes() {
      clearTimeout(this._reloadTimeout);
      this._reloadTimeout = setTimeout(() => {
        this.fetchLatestRun();
      }, 500);
    },
  },
};
</script>

<style scoped>
.parameters-section {
  background-color: #f7f7f7;
  padding: 15px;
  border-radius: 5px;
  margin-bottom: 20px;
}

.form-control-range {
  width: 100%;
}

.comments-cell {
  max-width: 400px;
  white-space: normal;
  word-break: break-word;
  font-size: 0.9em;
}

.comments-cell ol {
  margin: 0;
  padding-left: 20px;
}

.comments-cell li {
  margin-bottom: 5px;
}
</style>
