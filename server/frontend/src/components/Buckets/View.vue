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
                >Marked triaged until {{ bucket.hide_until | date }}.</span
              >
              <br v-if="canEdit" /><br v-if="canEdit" />
              <div v-if="canEdit" class="btn-group">
                <assignbutton :bucket="bucket.id" :providers="providers" />
                <a :href="bucket.new_bug_url" class="btn btn-danger"
                  >File a bug</a
                >
                <hidebucketbutton
                  v-if="!bucket.hide_until"
                  :bucket="bucket.id"
                />
                <a v-else v-on:click="unhide" class="btn btn-default"
                  >Unmark triaged</a
                >
              </div>
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
              <div class="btn-group">
                <a :href="reportsUrl" class="btn btn-default">View Reports</a>
                <a
                  title="Add/Update"
                  class="btn btn-danger"
                  v-on:click="submitWatchForm"
                  >Notify on New Reports</a
                >
              </div>
              <form :action="watchUrl" ref="bucketWatchForm" method="post">
                <input type="hidden" name="bucket" :value="bucket.id" />
                <input
                  type="hidden"
                  name="report"
                  :value="bucket.latest_entry_id"
                />
              </form>
            </td>
          </tr>
          <tr>
            <td>Latest Report</td>
            <td>{{ bucket.latest_report | date }}</td>
          </tr>
          <tr>
            <td>Priority</td>
            <td>{{ bucket.priority }}</td>
          </tr>
          <tr>
            <td>Signature</td>
            <td>
              <div id="signature" class="collapse">
                <pre><code>{{ prettySignature }}</code></pre>
              </div>
              <button
                aria-controls="signature"
                aria-expanded="false"
                class="btn btn-default btn-xs"
                data-target="#signature"
                data-toggle="collapse"
              >
                <span
                  aria-label="Show signature field"
                  class="bi bi-eye-fill"
                  title="Show signature field"
                ></span>
                <span
                  aria-label="Hide signature field"
                  class="bi bi-eye-slash-fill"
                  title="Hide signature field"
                ></span>
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="canEdit" class="btn-group">
        <a
          aria-label="Edit bucket"
          class="btn btn-default"
          :href="editUrl"
          title="Edit bucket"
          >Edit</a
        >
        <a
          aria-label="Delete bucket"
          class="btn btn-danger"
          :href="delUrl"
          title="Delete bucket"
          >Delete</a
        >
        <br />
        <br />
      </div>

      <div class="table-responsive">
        <table
          class="table table-condensed table-hover table-bordered table-db wrap-none"
        >
          <thead>
            <tr>
              <th>Date Reported</th>
              <th>URL</th>
              <th>User Comments</th>
              <th>App</th>
              <th>Channel</th>
              <th>Version</th>
              <th>Breakage Category</th>
              <th>OS</th>
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
import ClipLoader from "vue-spinner/src/ClipLoader.vue";
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
import * as api from "../../api";
import PageNav from "../PageNav.vue";
import ActivityGraph from "../ActivityGraph.vue";
import AssignBtn from "./AssignBtn.vue";
import HideBucketBtn from "./HideBucketBtn.vue";
import ReportPreviewRow from "./ReportPreviewRow.vue";

const pageSize = 10;

export default {
  components: {
    activitygraph: ActivityGraph,
    assignbutton: AssignBtn,
    ClipLoader: ClipLoader,
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
    const defaultSortKeys = ["-comments__length", "-reported_at"];
    return {
      currentEntries: "?",
      currentPage: 1,
      description: "",
      loading: true,
      reports: null,
      sortKeys: [...defaultSortKeys],
      totalPages: 1,
    };
  },
  filters: {
    date: date,
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
  mounted() {
    const el = document.getElementsByName("csrfmiddlewaretoken")[0];
    this.$refs.bucketWatchForm.appendChild(el);
  },
  methods: {
    buildQueryParams() {
      const result = {
        query: JSON.stringify({
          op: "AND",
          comments__length__gt: 0,
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
  },
  watch: {
    currentPage() {
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
</style>
