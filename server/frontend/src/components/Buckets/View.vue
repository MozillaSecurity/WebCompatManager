<template>
  <div class="panel panel-default">
    <div class="panel-heading"><i class="bi bi-tag-fill"></i> Bucket</div>
    <div class="panel-body">
      <table class="table">
        <tbody>
          <tr>
            <td>Description</td>
            <td>{{ bucket.description }}</td>
          </tr>
          <tr>
            <td>Triage Status</td>
            <td v-if="bucket.bug">
              <span v-if="bucket.bug_urltemplate">
                Reported as
                <a
                  :class="{
                    fixedbug: bucket.bug_closed,
                  }"
                  :href="bucket.bug_urltemplate"
                  target="_blank"
                  >bug {{ bucket.bug }}</a
                >.
              </span>
              <span v-else>
                Reported as bug {{ bucket.bug }} on {{ bucket.bug_hostname }}
              </span>
              <br v-if="canEdit" /><br v-if="canEdit" />
              <div v-if="canEdit" class="btn-group">
                <a v-on:click="unlink" class="btn btn-danger">Unlink</a>
              </div>
            </td>
            <td v-else>
              No bug associated.
              <span v-if="bucket.hide_until"
                >Marked triaged until {{ formatDate(bucket.hide_until) }}.</span
              >
              <br v-if="canEdit" /><br v-if="canEdit" />
              <div v-if="canEdit" class="btn-group">
                <assignbutton :bucket="bucket.id" :providers="providers" />
                <hidebucketbutton
                  v-if="!bucket.hide_until"
                  :bucket="bucket.id"
                />
                <a v-else v-on:click="unhide" class="btn btn-default"
                  >Unmark triaged</a
                >
              </div>
              <br v-if="canEdit" /><br v-if="canEdit" />
              <div v-if="canEdit" class="btn-group">
                <a
                  class="btn btn-success"
                  v-on:click="prepareSiteReport(reports)"
                >
                  Prepare new Site Report bug
                </a>
                <a
                  class="btn btn-success"
                  v-on:click="prepareETPStrictReport(reports)"
                >
                  Prepare new ETP Strict bug
                </a>
              </div>
            </td>
          </tr>
          <tr>
            <td>Known Bugs</td>
            <td>
              <a
                class="btn btn-default"
                :href="knownBugsUrl(bucket.domain)"
                target="_blank"
              >
                Show open bugs for this domain
              </a>
            </td>
          </tr>
          <tr>
            <td>Reports in this bucket</td>
            <td>
              {{ bucket.size }}
              <span
                v-if="bucket.reassign_in_progress"
                class="bi bi-hourglass-split"
                data-toggle="tooltip"
                data-placement="top"
                title="Reports are currently being reassigned in this bucket"
              ></span>
              <activitygraph
                :data="bucket.report_history"
                :range="activityRange"
              />
            </td>
          </tr>
          <tr>
            <td>ML Valid Probability Filter</td>
            <td>
              <div class="ml-filter-container">
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  v-model.number="mlValidThreshold"
                  class="ml-slider"
                />
                <span class="ml-threshold-value"
                  >≥ {{ mlValidThreshold.toFixed(2) }}</span
                >
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="table-responsive">
        <table
          class="table table-condensed table-hover table-bordered table-db wrap-none"
        >
          <thead>
            <tr>
              <th>Date Reported</th>
              <th>URL</th>
              <th>User Comments</th>
              <th>ML Label</th>
              <th>Product</th>
              <th>ETP &amp; PBM</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="8">
                <ClipLoader class="m-strong" :color="'black'" :size="'50px'" />
              </td>
            </tr>
            <ReportPreviewRow
              v-for="report in reports"
              :key="report.id"
              :report="report"
              v-else
            />
          </tbody>
        </table>
      </div>
      <PageNav
        :initial="currentPage"
        :pages="totalPages"
        v-on:page-changed="currentPage = $event"
      />
    </div>
  </div>
</template>

<script>
import _throttle from "lodash/throttle";
import LoadingSpinner from "../LoadingSpinner.vue";
import swal from "sweetalert";
import {
  E_SERVER_ERROR,
  assignExternalBug,
  date,
  errorParser,
  hideBucketUntil,
  jsonPretty,
  parseHash,
} from "../../helpers";
import {
  etpStrictReportDescription,
  newBugDefaultParams,
  openPrefilledBugzillaBug,
  siteReportDescription,
} from "../../prefilled_bug_helpers";
import * as api from "../../api";
import PageNav from "../PageNav.vue";
import ActivityGraph from "../ActivityGraph.vue";
import AssignBtn from "./AssignBtn.vue";
import HideBucketBtn from "./HideBucketBtn.vue";
import ReportPreviewRow from "./ReportPreviewRow.vue";

const pageSize = 50;

export default {
  components: {
    activitygraph: ActivityGraph,
    assignbutton: AssignBtn,
    ClipLoader: LoadingSpinner,
    hidebucketbutton: HideBucketBtn,
    PageNav: PageNav,
    ReportPreviewRow: ReportPreviewRow,
  },
  computed: {
    prettySignature() {
      return jsonPretty(this.bucket.signature);
    },
  },
  created: function () {
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
    }
    this.fetch();
  },
  data: function () {
    const defaultSortKeys = ["-reported_at"];
    return {
      currentEntries: "?",
      currentPage: 1,
      description: "",
      loading: true,
      mlValidThreshold: 0.8,
      reports: null,
      sortKeys: [...defaultSortKeys],
      totalPages: 1,
    };
  },
  props: {
    activityRange: {
      type: Number,
      required: true,
    },
    bucket: {
      type: Object,
      required: true,
    },
    reportsUrl: {
      type: String,
      required: true,
    },
    canEdit: {
      type: Boolean,
      required: true,
    },
    delUrl: {
      type: String,
      required: true,
    },
    editUrl: {
      type: String,
      required: true,
    },
    optUrl: {
      type: String,
      required: true,
    },
    providers: {
      type: Array,
      required: true,
    },
    watchUrl: {
      type: String,
      required: true,
    },
  },
  mounted() {},
  methods: {
    formatDate: date,
    buildQueryParams() {
      const result = {
        query: JSON.stringify({
          op: "AND",
          comments__length__gt: 0,
          ml_valid_probability__gt: this.mlValidThreshold,
          bucket_id: this.bucket.id,
        }),
      };
      result.vue = "1";
      result.limit = pageSize;
      result.offset = `${(this.currentPage - 1) * pageSize}`;
      result.ordering = this.sortKeys.join();
      return result;
    },
    submitWatchForm() {
      this.$refs.bucketWatchForm.submit();
    },
    unhide() {
      hideBucketUntil(this.bucket.id, null)
        .then((data) => {
          window.location.href = data.url;
        })
        .catch((err) => {
          swal("Oops", errorParser(err), "error");
        });
    },
    unlink() {
      swal({
        title: "Unlink bug",
        text: "Are you sure that you want to unlink this signature from its assigned external bug?",
        buttons: true,
      }).then((value) => {
        if (value) {
          assignExternalBug(this.bucket.id, null, null)
            .then((data) => {
              window.location.href = data.url;
            })
            .catch((err) => {
              swal("Oops", errorParser(err), "error");
            });
        }
      });
    },
    fetch: _throttle(
      async function () {
        this.loading = true;
        this.reports = null;
        try {
          const data = await api.listReports(this.buildQueryParams());
          this.reports = data.results;
          this.currentEntries = this.reports.length;
          this.totalEntries = data.count;
          this.totalPages = Math.max(
            Math.ceil(this.totalEntries / pageSize),
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
            // eslint-disable-next-line no-console
            console.debug(err.response.data);
            swal("Oops", E_SERVER_ERROR, "error");
            this.loading = false;
          } else {
            // if the page loaded, but the fetch failed, either the network went away or we need to refresh auth
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
    updateHash: function () {
      let hash = {};
      if (this.currentPage !== 1) {
        hash.page = this.currentPage;
      }
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
    knownBugsUrl(domain) {
      const searchParams = new URLSearchParams([
        ["bug_file_loc_type", "allwordssubstr"],
        ["bug_file_loc", domain],
        ["query_format", "advanced"],
        ["resolution", "---"],
        ["j_top", "OR"],
        ["f1", "OP"],
        ["o2", "equals"],
        ["f2", "product"],
        ["v2", "Web Compatibility"],
        ["o3", "equals"],
        ["f3", "component"],
        ["v3", "Site Reports"],
        ["f4", "CP"],
        ["f5", "OP"],
        ["o6", "equals"],
        ["f6", "product"],
        ["v6", "Web Compatibility"],
        ["o7", "equals"],
        ["f7", "component"],
        ["v7", "Privacy: Site Reports"],
        ["f8", "CP"],
        ["f9", "OP"],
        ["o10", "substring"],
        ["f10", "keywords"],
        ["v10", "webcompat:site-report"],
        ["f11", "CP"],
      ]);

      const url = new URL("https://bugzilla.mozilla.org/buglist.cgi");
      url.search = searchParams.toString();
      return url.toString();
    },
    prepareSiteReport(reports) {
      const searchParams = newBugDefaultParams(reports[0]);
      searchParams.append("component", "Site Reports");
      searchParams.append("comment", siteReportDescription(reports[0]));
      openPrefilledBugzillaBug(searchParams);
    },
    prepareETPStrictReport(reports) {
      const searchParams = newBugDefaultParams(reports[0]);
      searchParams.append("component", "Privacy: Site Reports");
      searchParams.append("comment", etpStrictReportDescription(reports[0]));
      searchParams.append("dependson", "tp-breakage");
      openPrefilledBugzillaBug(searchParams);
    },
  },
  watch: {
    currentPage() {
      this.fetch();
    },
    mlValidThreshold() {
      this.currentPage = 1;
      this.fetch();
    },
    sortKeys() {
      this.fetch();
    },
  },
};
</script>

<style scoped>
form {
  display: inline;
}
button[aria-expanded="true"] .bi-eye-fill {
  display: none;
}
button[aria-expanded="false"] .bi-eye-slash-fill {
  display: none;
}
.ml-filter-container {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ml-slider {
  flex: 1;
  max-width: 300px;
}
.ml-threshold-value {
  font-weight: bold;
  min-width: 60px;
}
</style>
