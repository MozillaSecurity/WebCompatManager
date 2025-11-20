<template>
  <div class="panel panel-default">
    <div class="panel-heading">
      <i class="bi bi-activity"></i> Spikes
    </div>
    <div class="panel-body">
      <div v-if="selectedRun">
        <p>
          {{ filteredSpikes.length }} spikes in window <strong>{{ shortWindowPeriod }}</strong>
        </p>
        <div class="form-group">
          <label>
            Min reports with non-empty comments: <strong>{{ minCommentsFilter }}</strong>
          </label>
          <input
            type="range"
            class="mc-slider"
            v-model.number="minCommentsFilter"
            :min="0"
            :max="maxCommentsCount"
            step="1"
          />
        </div>
      </div>

      <div v-if="loading" class="text-center">
        <i class="bi bi-hourglass-split"></i> Loading...
      </div>
      <div v-else-if="filteredSpikes.length === 0" class="text-muted">
        No spikes detected in the latest run.
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
            <td>{{ spike.bucket_domain || '(no domain)' }}</td>
            <td class="text-right">{{ spike.short_count }}</td>
            <td class="text-right">{{ spike.short_count_with_comments }}</td>
            <td class="text-right">{{ spike.short_average.toFixed(2) }}</td>
            <td class="text-right">{{ spike.long_average.toFixed(2) }}</td>
            <td class="text-right">{{ spike.ratio.toFixed(2) }}</td>
            <td class="comments-cell">
              <ol v-if="spike.report_comments && spike.report_comments.length > 0">
                <li v-for="(comment, index) in spike.report_comments" :key="index">{{ comment }}</li>
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
import * as api from '../../api';

export default {
  name: 'SpikesList',
  data() {
    return {
      loading: false,
      selectedRun: null,
      spikes: [],
      minCommentsFilter: 3
    };
  },
  computed: {
    shortWindowPeriod() {
      if (!this.selectedRun) return 'No run selected';
      return `${this.selectedRun.short_window_start} to ${this.selectedRun.short_window_end}`;
    },
    filteredSpikes() {
      return this.spikes.filter(spike =>
        spike.short_count_with_comments >= this.minCommentsFilter
      );
    },
    maxCommentsCount() {
      if (this.spikes.length === 0) return 0;
      return Math.max(...this.spikes.map(s => s.short_count_with_comments));
    }
  },
  async mounted() {
    await this.fetchLatestRun();
  },
  methods: {
    async fetchLatestRun() {
      this.loading = true;
      try {
        const run = await api.getLatestSpikeDetectionRun();
        if (run) {
          this.selectedRun = {
            id: run.id,
            threshold: run.threshold,
            short_window_start: run.short_window_start,
            short_window_end: run.short_window_end
          };
          this.spikes = run.spikes || [];
        }
      } catch (err) {
        console.error('Error fetching spike detection runs:', err);
      }
      this.loading = false;
    }
  }
};
</script>

<style scoped>
.mc-slider {
  max-width: 300px;
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
