<template>
  <div class="panel panel-default">
    <div class="panel-heading"><i class="bi bi-tag-fill"></i> Buckets</div>
    <div class="panel-body">
      <div v-if="!advancedQuery">
        <div class="btn-group" role="group">
          <a :href="createBucketUrl" class="btn btn-success" v-if="canEdit"
            >Create bucket</a
          >
          <button
            type="button"
            class="btn btn-default"
            :disabled="loading"
            v-on:click="updateShowLogged"
          >
            {{ showLogged ? "Hide Logged" : "Show Logged" }}
          </button>
          <button
            type="button"
            class="btn btn-default"
            :disabled="loading"
            v-on:click="updateShowHidden"
          >
            {{ showHidden ? "Hide Triaged" : "Show Triaged" }}
          </button>
        </div>
        <p></p>
        <a
          title="Show advanced query for the current search/filters"
          class="pointer"
          v-on:click="showAdvancedQuery"
          >Advanced query</a
        ><br />
      </div>
      <div v-else>
        <div v-if="canEdit" class="btn-group" role="group">
          <a :href="createBucketUrl" class="btn btn-success">Create bucket</a>
        </div>
        <p v-if="canEdit"></p>
        <label for="id_query">Search Query</label>
        <HelpJSONQueryPopover
          :parameters="[
            { name: 'id', type: 'Integer (ID)' },
            { name: 'bug', type: 'Integer (ID)' },
            { name: 'bug__closed', type: 'Date' },
            { name: 'bug__external_id', type: 'String' },
            { name: 'bug__external_type', type: 'Integer (ID)' },
            { name: 'bug__external_type__classname', type: 'String' },
            { name: 'bug__external_type__hostname', type: 'String' },
            { name: 'description', type: 'String' },
            { name: 'priority', type: 'Integer' },
            { name: 'signature', type: 'String' },
            { name: 'size', type: 'Integer' },
          ]"
        />
        <textarea
          id="id_query"
          class="form-control"
          name="query"
          spellcheck="false"
          :rows="(queryStr.match(/\n/g) || '').length + 1"
          v-model="queryStr"
        ></textarea>
        <br v-if="queryError" />
        <div v-if="queryError" class="alert alert-warning" role="alert">
          {{ queryError }}
        </div>
        <a class="pointer" v-on:click="hideAdvancedQuery">Hide advanced query</a
        ><br />
        <button
          v-on:click="fetch"
          :disabled="!modified || loading"
          :title="queryButtonTitle"
        >
          Query
        </button>
      </div>
      <br />
      <p>
        <span v-if="showLogged">
          Displaying {{ currentEntries }}/{{ totalEntries }} buckets in the
          database
        </span>
        <span v-else>
          Displaying {{ currentEntries }}/{{ totalEntries }} unlogged buckets in
          the database
        </span>
        (<span v-if="showHidden">including</span>
        <span v-else>excluding</span>
        triaged).
      </p>

      <PageNav
        :initial="currentPage"
        :pages="totalPages"
        :show="5"
        v-on:page-changed="currentPage = $event"
      />
    </div>
    <div class="table-responsive">
      <table class="table table-condensed table-hover table-bordered table-db">
        <thead>
          <tr>
            <th
              v-on:click.exact="sortBy('id')"
              v-on:click.ctrl.exact="addSort('id')"
              :class="{
                active: sortKeys.includes('id') || sortKeys.includes('-id'),
              }"
            >
              ID
            </th>
            <th
              v-on:click.exact="sortBy('description')"
              v-on:click.ctrl.exact="addSort('description')"
              :class="{
                active:
                  sortKeys.includes('description') ||
                  sortKeys.includes('-description'),
              }"
            >
              Description
            </th>
            <th
              v-on:click.exact="sortBy('priority')"
              v-on:click.ctrl.exact="addSort('priority')"
              :class="{
                active:
                  sortKeys.includes('priority') ||
                  sortKeys.includes('-priority'),
              }"
            >
              Priority
            </th>
            <th>Activity</th>
            <th
              v-on:click.exact="sortBy('latest_report')"
              v-on:click.ctrl.exact="addSort('latest_report')"
              :class="{
                active:
                  sortKeys.includes('latest_report') ||
                  sortKeys.includes('-latest_report'),
              }"
            >
              Latest Report
            </th>
            <th
              v-on:click.exact="sortBy('size')"
              v-on:click.ctrl.exact="addSort('size')"
              :class="{
                active: sortKeys.includes('size') || sortKeys.includes('-size'),
              }"
            >
              Size
            </th>
            <th
              v-on:click.exact="sortBy('bug__external_id')"
              v-on:click.ctrl.exact="addSort('bug__external_id')"
              :class="{
                active:
                  sortKeys.includes('bug__external_id') ||
                  sortKeys.includes('-bug__external_id'),
              }"
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
            :activity-range="activityRange"
            :can-edit="canEdit"
            :key="bucket.id"
            :providers="providers"
            :bucket="bucket"
            v-else
          />
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import _throttle from "lodash/throttle";
import _isEqual from "lodash/isEqual";
import ClipLoader from "vue-spinner/src/ClipLoader.vue";
import { errorParser, multiSort, parseHash } from "../../helpers";
import * as api from "../../api";
import PageNav from "../PageNav.vue";
import Row from "./Row.vue";
import HelpJSONQueryPopover from "../HelpJSONQueryPopover.vue";

export default {
  mixins: [multiSort],
  components: {
    ClipLoader,
    HelpJSONQueryPopover,
    PageNav,
    Row,
  },
  props: {
    activityRange: {
      type: Number,
      required: true,
    },
    canEdit: {
      type: Boolean,
      required: true,
    },
    createBucketUrl: {
      type: String,
      required: true,
    },
    watchUrl: {
      type: String,
      required: true,
    },
    providers: {
      type: Array,
      required: true,
    },
  },
  data: function () {
    const validSortKeys = [
      "bug__external_id",
      "id",
      "description",
      "latest_report",
      "priority",
      "size",
    ];
    const defaultSortKeys = ["-size", "-latest_report"];

    return {
      advancedQuery: false,
      buckets: [],
      currentEntries: "?",
      currentPage: 1,
      defaultSortKeys: defaultSortKeys,
      loading: false,
      modifiedCache: {},
      pageSize: 100,
      queryError: "",
      queryStr: JSON.stringify(
        { op: "AND", bug__isnull: true, hide_until__isnull: true },
        null,
        2,
      ),
      searchStr: "",
      sortKeys: [...defaultSortKeys],
      totalEntries: "?",
      totalPages: 1,
      validSortKeys: validSortKeys,
    };
  },
  created() {
    if (this.$route.query.all)
      this.queryStr = JSON.stringify({ op: "AND" }, null, 2);
    if (this.$route.query.ids)
      this.queryStr = JSON.stringify(
        { op: "AND", id__in: this.$route.query.ids.split(",") },
        null,
        2,
      );
    if (this.$route.hash.startsWith("#")) {
      const hash = parseHash(this.$route.hash);
      if (Object.prototype.hasOwnProperty.call(hash, "page")) {
        try {
          this.currentPage = Number.parseInt(hash.page, 10);
        } catch (e) {
          // eslint-disable-next-line no-console
          console.debug(`parsing '#page=\\d+': ${e}`);
        }
      }
      if (Object.prototype.hasOwnProperty.call(hash, "query")) {
        this.queryStr = JSON.stringify(JSON.parse(hash.query || ""), null, 2);
      }
    }
    this.fetch();
  },
  computed: {
    modified() {
      const queryStr = (() => {
        try {
          return JSON.parse(this.queryStr);
        } catch (e) {} // eslint-disable-line no-empty
      })();
      return !_isEqual(queryStr, this.modifiedCache.queryStr);
    },
    orderedBuckets() {
      return this.sortData(this.buckets);
    },
    queryButtonTitle() {
      if (this.loading) return "Query in progress";
      if (!this.modified) return "Results match current query";
      return "Submit query";
    },
    showLogged() {
      return !this.queryStr.includes('"bug__isnull": true');
    },
    showHidden() {
      return !this.queryStr.includes('"hide_until__isnull": true');
    },
  },
  methods: {
    hideAdvancedQuery() {
      this.advancedQuery = false;
    },
    showAdvancedQuery() {
      this.advancedQuery = true;
    },
    updateShowLogged() {
      if (this.showLogged) {
        this.queryStr = JSON.stringify(
          Object.assign({ bug__isnull: true }, JSON.parse(this.queryStr)),
          null,
          2,
        );
      } else {
        const query = JSON.parse(this.queryStr);
        delete query["bug__isnull"];
        this.queryStr = JSON.stringify(query, null, 2);
      }
      this.fetch();
    },
    updateShowHidden() {
      if (this.showHidden) {
        this.queryStr = JSON.stringify(
          Object.assign(
            { hide_until__isnull: true },
            JSON.parse(this.queryStr),
          ),
          null,
          2,
        );
      } else {
        const query = JSON.parse(this.queryStr);
        delete query["hide_until__isnull"];
        this.queryStr = JSON.stringify(query, null, 2);
      }
      this.fetch();
    },
    buildParams() {
      return {
        vue: "1",
        limit: this.pageSize,
        offset: `${(this.currentPage - 1) * this.pageSize}`,
        ordering: this.sortKeys.join(),
        query: this.queryStr,
      };
    },
    updateModifiedCache() {
      this.modifiedCache.ignoreToolFilter = this.ignoreToolFilter;
      try {
        // ignore query errors
        this.modifiedCache.queryStr = JSON.parse(this.queryStr);
      } catch (e) {} // eslint-disable-line no-empty
    },
    fetch: _throttle(
      async function () {
        this.loading = true;
        this.updateModifiedCache();
        this.buckets = null;
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
          if (this.currentPage > this.totalPages) {
            this.currentPage = this.totalPages;
            return;
          }
          this.updateHash();
        } catch (err) {
          if (
            err.response &&
            err.response.status === 400 &&
            err.response.data
          ) {
            this.queryError = err.response.data.detail;
            this.loading = false;
          } else {
            // if the page loaded, but the fetch failed, either the network went away or
            // we need to refresh auth
            // eslint-disable-next-line no-console
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
    updateHash() {
      let hash = {};
      if (this.currentPage !== 1) {
        hash.page = this.currentPage;
      }
      this.updateHashSort(hash);
      if (this.queryStr) hash.query = encodeURIComponent(this.queryStr);
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
.pointer {
  cursor: pointer;
}
</style>
