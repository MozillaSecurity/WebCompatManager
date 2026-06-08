<template>
  <div class="panel panel-default">
    <div class="panel-heading"><i class="bi bi-tag-fill"></i> Buckets</div>
    <div class="panel-body">
      <!-- Simple filter mode -->
      <div v-if="!advancedMode">
        <StatusFilter
          :active-state="activeState"
          :triage-status="triageStatus"
          :triage-status-options="triageStatusOptions"
          :disabled="loading"
          @filter-change="onFilterChange"
        />
        <FilterBar
          :query-str="queryStr"
          :countries="countries"
          :labels="labels"
          :error="queryError"
          :disabled="loading"
          @filter-change="onFilterChange"
          @query-input="queryStr = $event"
          @show-advanced="showAdvancedQuery"
        />
      </div>

      <!-- Advanced query mode -->
      <QueryEditor
        v-else
        v-model="advancedQueryStr"
        :error="queryError"
        :loading="loading"
        @run="fetch"
        @close="hideAdvancedQuery"
      />

      <br />
      <p>Displaying {{ currentEntries }}/{{ totalEntries }} buckets.</p>

      <PageNav
        :initial="currentPage"
        :pages="totalPages"
        :show="5"
        @page-changed="currentPage = $event"
      />
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
              ID
            </th>
            <th
              :class="{
                active:
                  sortKeys.includes('description') ||
                  sortKeys.includes('-description'),
              }"
              @click.exact="sortBy('description')"
              @click.ctrl.exact="addSort('description')"
            >
              Description
            </th>
            <th>Representative Comment</th>
            <th>Activity</th>
            <th
              :class="{
                active:
                  sortKeys.includes('priority_score') ||
                  sortKeys.includes('-priority_score'),
              }"
              @click.exact="sortBy('priority_score')"
              @click.ctrl.exact="addSort('priority_score')"
            >
              Priority Score
            </th>
            <th
              :class="{
                active:
                  sortKeys.includes('latest_report') ||
                  sortKeys.includes('-latest_report'),
              }"
              @click.exact="sortBy('latest_report')"
              @click.ctrl.exact="addSort('latest_report')"
            >
              Latest Report
            </th>
            <th
              :class="{
                active: sortKeys.includes('size') || sortKeys.includes('-size'),
              }"
              @click.exact="sortBy('size')"
              @click.ctrl.exact="addSort('size')"
            >
              Size
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
              Details
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="9">
              <ClipLoader class="m-strong" :color="'black'" :size="'50px'" />
            </td>
          </tr>
          <Row
            v-for="bucket in orderedBuckets"
            v-else
            :key="bucket.id"
            :activity-range="activityRange"
            :can-edit="canEdit"
            :providers="providers"
            :bucket="bucket"
          />
        </tbody>
      </table>
    </div>
    <div class="panel-footer" v-if="!loading && buckets.length > 10">
      <PageNav
        :initial="currentPage"
        :pages="totalPages"
        :show="5"
        @page-changed="currentPage = $event"
      />
    </div>
  </div>
</template>

<script>
import _throttle from "lodash/throttle";
import LoadingSpinner from "../LoadingSpinner.vue";
import { errorParser, multiSort, parseHash } from "../../helpers";
import {
  buildQuery,
  buildBucketHash,
  BUCKET_STATES,
  validateQL,
} from "../../bucket_filter";
import * as api from "../../api";
import PageNav from "../PageNav.vue";
import Row from "./Row.vue";
import StatusFilter from "./StatusFilter.vue";
import FilterBar from "./FilterBar.vue";
import QueryEditor from "./QueryEditor.vue";

export default {
  components: {
    ClipLoader: LoadingSpinner,
    StatusFilter,
    FilterBar,
    PageNav,
    QueryEditor,
    Row,
  },
  mixins: [multiSort],
  props: {
    activityRange: { type: Number, required: true },
    canEdit: { type: Boolean, required: true },
    watchUrl: { type: String, required: true },
    providers: { type: Array, required: true },
    countries: { type: Array, default: () => [] },
    labels: { type: Array, default: () => [] },
  },
  data() {
    const validSortKeys = [
      "bug__external_id",
      "id",
      "description",
      "latest_report",
      "priority_score",
      "size",
    ];
    const defaultSortKeys = ["-priority_score", "-size", "-latest_report"];
    return {
      activeState: "needs_triage",
      advancedMode: false,
      advancedQueryStr: "",
      buckets: [],
      currentEntries: "?",
      currentPage: 1,
      defaultSortKeys,
      loading: false,
      pageSize: 100,
      queryError: "",
      queryStr: "",
      sortKeys: [...defaultSortKeys],
      totalEntries: "?",
      totalPages: 1,
      triageStatus: null,
      triageStatusOptions: [],
      validSortKeys,
    };
  },
  computed: {
    orderedBuckets() {
      return this.sortData(this.buckets);
    },
  },
  created() {
    if (this.$route.query.all) {
      this.activeState = "all";
    }
    if (this.$route.hash.startsWith("#")) {
      const hash = parseHash(this.$route.hash);
      if (hash.page) {
        try {
          this.currentPage = Number.parseInt(hash.page, 10);
        } catch (e) {
          console.debug(`parsing '#page=\\d+': ${e}`);
        }
      }
      if (hash.state in BUCKET_STATES) {
        this.activeState = hash.state;
      }
      if (hash.triage_status) {
        this.triageStatus = hash.triage_status;
      }
      if (hash.q) {
        this.queryStr = hash.q;
      }
    }
    this.fetch();
  },
  methods: {
    onFilterChange(update) {
      Object.assign(this, update);
      this.currentPage = 1;
      this.fetch();
    },
    showAdvancedQuery() {
      this.advancedQueryStr = buildQuery({
        activeState: this.activeState,
        queryStr: this.queryStr,
        triageStatus: this.triageStatus,
      });
      this.advancedMode = true;
    },
    hideAdvancedQuery() {
      this.advancedMode = false;
    },
    buildParams() {
      const query = this.advancedMode
        ? this.advancedQueryStr
        : buildQuery({
            activeState: this.activeState,
            queryStr: this.queryStr,
            triageStatus: this.triageStatus,
          });
      return {
        vue: "1",
        limit: this.pageSize,
        offset: `${(this.currentPage - 1) * this.pageSize}`,
        ordering: this.sortKeys.join(),
        query,
      };
    },
    fetch: _throttle(
      async function () {
        if (!this.advancedMode) {
          const { valid, error } = validateQL(this.queryStr);
          if (!valid) {
            this.queryError = error;
            this.buckets = [];
            return;
          }
        }
        this.loading = true;
        this.buckets = [];
        this.queryError = "";
        try {
          const data = await api.listBuckets(this.buildParams());
          this.buckets = data.results;
          this.currentEntries = this.buckets.length;
          this.totalEntries = data.count;
          this.totalPages = Math.max(
            Math.ceil(this.totalEntries / this.pageSize),
            1,
          );
          if (!this.triageStatusOptions.length && data.results.length) {
            this.triageStatusOptions =
              data.results[0].triage_status_choices ?? [];
          }
          if (this.currentPage > this.totalPages) {
            this.currentPage = this.totalPages;
            return;
          }
          this.updateHash();
        } catch (err) {
          if (err.response?.status === 400 && err.response?.data) {
            this.queryError = err.response.data.detail;
          } else {
            // if the page loaded, but the fetch failed, either the network went away or
            // we need to refresh auth

            console.debug(errorParser(err));
            this.$router.go(0);
          }
        } finally {
          this.loading = false;
        }
      },
      500,
      { trailing: true },
    ),
    updateHash() {
      const hashSort = {};
      this.updateHashSort(hashSort);
      const routeHash = buildBucketHash({
        activeState: this.activeState,
        queryStr: this.queryStr,
        triageStatus: this.triageStatus,
        currentPage: this.currentPage,
        sort: hashSort.sort,
      });
      if (this.$route.hash !== routeHash) {
        this.$router.push({ path: this.$route.path, hash: routeHash });
      }
    },
  },
  watch: {
    currentPage() {
      this.fetch();
    },
    sortKeys() {
      this.updateHash();
    },
  },
};
</script>

<style scoped>
.m-strong {
  margin-top: 1.5rem;
  margin-bottom: 1.5rem;
}
</style>
