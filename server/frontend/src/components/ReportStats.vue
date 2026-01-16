<template>
  <div class="panel panel-default">
    <div class="panel-heading">
      <i class="bi bi-bar-chart-fill"></i> Statistics
    </div>
    <div class="panel-body">
      <div>
        Total reports in:<br />
        ... last day: {{ totals[0] }}<br />
        ... last week: {{ totals[1] }}<br />
        ... last month: {{ totals[2] }}
      </div>
    </div>
    <div class="panel-body">
      <reportstatsgraph :data="graphData" />
    </div>
    <div class="table-responsive">
      <table class="table table-condensed table-hover table-bordered table-db">
        <thead>
          <tr>
            <th
              :class="{
                active: sortKeys.includes('id') || sortKeys.includes('-id'),
              }"
              @click.exact="sortBy('id')"
              @click.ctrl.exact="addSort('id')"
            >
              Bucket
            </th>
            <th
              :class="{
                active:
                  sortKeys.includes('description') ||
                  sortKeys.includes('description'),
              }"
              @click.exact="sortBy('description')"
              @click.ctrl.exact="addSort('description')"
            >
              Short Description
            </th>
            <th>Activity</th>
            <th
              :class="{
                active:
                  sortKeys.includes('counts[0]') ||
                  sortKeys.includes('-counts[0]'),
              }"
              @click.exact="sortBy('counts[0]')"
              @click.ctrl.exact="addSort('counts[0]')"
            >
              Reports (last day)
            </th>
            <th
              :class="{
                active:
                  sortKeys.includes('counts[1]') ||
                  sortKeys.includes('-counts[1]'),
              }"
              @click.exact="sortBy('counts[1]')"
              @click.ctrl.exact="addSort('counts[1]')"
            >
              Reports (last week)
            </th>
            <th
              :class="{
                active:
                  sortKeys.includes('counts[2]') ||
                  sortKeys.includes('-counts[2]'),
              }"
              @click.exact="sortBy('counts[2]')"
              @click.ctrl.exact="addSort('counts[2]')"
            >
              Reports (last month)
            </th>
            <th
              :class="{
                active:
                  sortKeys.includes('bug__external_id') ||
                  sortKeys.includes('-bug__external_id'),
              }"
              @click.exact="sortBy('bug__external_id')"
              @click.ctrl.exact="addSort('bug__external_id')"
            >
              External Bug
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="7">
              <ClipLoader class="m-strong" :color="'black'" :size="'50px'" />
            </td>
          </tr>
          <tr v-for="bucket of sortedBucketData" v-else :key="bucket.id">
            <td>
              <a title="View bucket" :href="bucket.view_url">{{ bucket.id }}</a>
            </td>
            <td class="wrap-anywhere">
              <span class="two-line-limit">{{ bucket.description }}</span>
            </td>
            <td>
              <activitygraph
                :data="bucket.report_history"
                :range="activityRange"
              />
            </td>
            <td>{{ bucket.counts[0] }}</td>
            <td>{{ bucket.counts[1] }}</td>
            <td>{{ bucket.counts[2] }}</td>
            <td>
              <a
                v-if="bucket.bug && bucket.bug_urltemplate"
                :class="{ fixedbug: bucket.bug_closed }"
                :href="bucket.bug_urltemplate"
                target="_blank"
              >
                {{ bucket.bug }}
              </a>
              <p v-else-if="bucket.bug">
                {{ bucket.bug }} on {{ bucket.bug_hostname }}
              </p>
              <assignbutton
                v-else-if="canEdit"
                :bucket="bucket.id"
                :providers="providers"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import _throttle from "lodash/throttle";
import swal from "sweetalert";
import LoadingSpinner from "./LoadingSpinner.vue";
import { errorParser, E_SERVER_ERROR, multiSort } from "../helpers";
import * as api from "../api";
import AssignBtn from "./Buckets/AssignBtn.vue";
import ActivityGraph from "./ActivityGraph.vue";
import ReportStatsGraph from "./ReportStatsGraph.vue";

export default {
  components: {
    ClipLoader: LoadingSpinner,
    activitygraph: ActivityGraph,
    assignbutton: AssignBtn,
    reportstatsgraph: ReportStatsGraph,
  },
  mixins: [multiSort],
  props: {
    activityRange: {
      type: Number,
      required: true,
    },
    canEdit: {
      type: Boolean,
      required: true,
    },
    providers: {
      type: Array,
      required: true,
    },
  },
  data: function () {
    const defaultSortKeys = ["-counts[0]"];
    const validSortKeys = [
      "bug__external_id",
      "counts[0]",
      "counts[1]",
      "counts[2]",
      "id",
      "description",
    ];
    return {
      defaultSortKeys: defaultSortKeys,
      graphData: [],
      loading: false,
      // [Bucket()]
      bucketData: [],
      sortKeys: [...defaultSortKeys],
      // [day, week, month]
      totals: [],
      validSortKeys: validSortKeys,
    };
  },
  computed: {
    sortedBucketData: function () {
      return this.sortData(this.bucketData);
    },
  },
  created: function () {
    this.fetch();
  },
  methods: {
    // get stats
    fetch: _throttle(
      async function () {
        this.loading = true;
        this.updateHash();
        try {
          // fetch stats
          const stats = await api.reportStats();

          // process result
          this.totals = stats.totals;
          this.graphData = stats.graph_data;

          // then get buckets for those stats
          if (Object.keys(stats.frequent_buckets).length) {
            const bucketData = await api.listBuckets({
              vue: "1",
              query: JSON.stringify({
                op: "AND",
                id__in: Object.keys(stats.frequent_buckets),
              }),
            });
            Object.keys(stats.frequent_buckets).forEach((x) =>
              bucketData.results.forEach((b) => {
                if (b.id == x) b.counts = stats.frequent_buckets[x];
              }),
            );
            this.bucketData = bucketData.results;
          } else {
            this.bucketData = [];
          }
        } catch (err) {
          if (
            err.response &&
            err.response.status === 400 &&
            err.response.data
          ) {
            swal("Oops", E_SERVER_ERROR, "error");
            this.loading = false;
          } else {
            // if the page loaded, but the fetch failed, either the network went away or we need to refresh auth

            console.debug(errorParser(err));
            this.$router.go(0);
            return;
          }
        }
        this.loading = false;
      },
      500,
      { trailing: true },
    ),
    updateHash: function () {
      const hash = {};

      this.updateHashSort(hash);
      if (Object.entries(hash).length) {
        const routeHash =
          "#" +
          Object.entries(hash)
            .map((kv) => kv.join("="))
            .join("&");
        if (this.$route.hash !== routeHash)
          this.$router.push({ path: this.$route.path, hash: routeHash });
      } else {
        if (this.$route.hash !== "")
          this.$router.push({ path: this.$route.path, hash: "" });
      }
    },
  },
  watch: {
    sortKeys() {
      this.updateHash();
    },
  },
};
</script>
