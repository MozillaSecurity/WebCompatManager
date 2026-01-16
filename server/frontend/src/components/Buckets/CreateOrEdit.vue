<template>
  <div class="panel panel-info">
    <div class="panel-heading">
      <i class="bi bi-tag-fill"></i>
      {{ bucketId ? "Edit Bucket" : "New Bucket" }}
    </div>
    <div class="panel-body">
      <div v-if="loading === 'preview'" class="alert alert-info" role="alert">
        Loading preview...
      </div>
      <div v-if="warning" class="alert alert-warning" role="alert">
        {{ warning }}
      </div>

      <p v-if="inList.length">
        New issues that will be assigned to this bucket (<a href="#reports_in"
          >list</a
        >):
        <span class="badge">{{ inListCount }}</span>
      </p>
      <p v-if="outList.length">
        Issues that will be removed from this bucket (<a href="#reports_out"
          >list</a
        >):
        <span class="badge">{{ outListCount }}</span>
      </p>

      <form @submit.prevent="">
        <label for="id_bucketDescription">Description</label><br />
        <input
          id="id_bucketDescription"
          v-model="bucket.description"
          class="form-control"
          maxlength="1023"
          type="text"
        />
        <br />

        <label for="id_signature">Signature</label>
        <HelpSignaturePopover /><br />
        <textarea
          id="id_signature"
          v-model="bucket.signature"
          class="form-control"
          spellcheck="false"
        ></textarea>

        <div class="field">
          <input id="id_reassign" v-model="reassign" type="checkbox" />
          <label for="id_reassign">
            Reassign matching reports (reports in this bucket and lower-priority
            buckets will be reassigned)
          </label>
        </div>
        <label for="id_priority">Priority</label>
        <input
          id="id_priority"
          v-model="bucket.priority"
          class="form-inline"
          type="number"
          min="-2"
          max="2"
        />
        <br /><br />

        <div v-if="bucketId" class="btn-group">
          <button
            type="submit"
            class="btn btn-success"
            :disabled="loading"
            @click="create_or_update(true)"
          >
            {{ loading === "save" ? "Saving..." : "Save" }}
          </button>
          <button
            type="submit"
            class="btn btn-default"
            :disabled="loading"
            @click="create_or_update(false)"
          >
            {{ loading === "preview" ? "Loading preview..." : "Preview" }}
          </button>
        </div>
        <div v-else class="btn-group">
          <button
            type="submit"
            class="btn btn-success"
            :disabled="loading"
            @click="create_or_update(true)"
          >
            {{ loading === "create" ? "Creating..." : "Create" }}
          </button>
          <button
            type="submit"
            class="btn btn-default"
            :disabled="loading"
            @click="create_or_update(false)"
          >
            {{ loading === "preview" ? "Loading preview..." : "Preview" }}
          </button>
        </div>
      </form>

      <div class="field">
        <template v-if="inList.length">
          <label id="reports_in">
            New issues that will be assigned to this bucket
            {{ inListCount > inList.length ? " (truncated)" : "" }}:
          </label>
          <List :entries="inList" />
        </template>

        <template v-if="outList.length">
          <label id="reports_out">
            Issues that will be removed from this bucket
            {{ outListCount > outList.length ? " (truncated)" : "" }}:
          </label>
          <List :entries="outList" />
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import { errorParser, jsonPretty } from "../../helpers";
import * as api from "../../api";
import List from "./ReportEntries/List.vue";
import HelpSignaturePopover from "../HelpSignaturePopover.vue";

export default {
  components: {
    HelpSignaturePopover,
    List,
  },
  props: {
    bucketId: {
      type: Number,
      default: null,
    },
    proposedSignature: {
      type: Object,
      default: null,
    },
    proposedDescription: {
      type: String,
      default: null,
    },
    warningMessage: {
      type: String,
      default: null,
    },
  },
  data: () => ({
    bucket: {
      description: "",
      priority: 0,
      signature: jsonPretty('{ "symptoms": [] }'),
    },
    reassign: true,
    warning: "",
    inList: [],
    inListCount: 0,
    outList: [],
    outListCount: 0,
    loading: null,
  }),
  async mounted() {
    if (this.bucketId) this.bucket = await api.retrieveBucket(this.bucketId);
    if (this.proposedSignature)
      this.bucket.signature = jsonPretty(this.proposedSignature);
    else if (this.bucketId)
      this.bucket.signature = jsonPretty(this.bucket.signature);
    if (this.proposedDescription)
      this.bucket.description = this.proposedDescription;
    if (this.warningMessage) this.warning = this.warningMessage;
  },
  methods: {
    async create_or_update(save) {
      this.warning = null;
      this.loading = save ? (this.bucketId ? "save" : "create") : "preview";
      const payload = {
        description: this.bucket.description,
        priority: this.bucket.priority,
        signature: this.bucket.signature,
      };

      try {
        let offset = 0;
        while (offset !== null) {
          const data = await (async () => {
            if (this.bucketId)
              return api.updateBucket({
                id: this.bucketId,
                params: { save: save, reassign: this.reassign, offset: offset },
                ...payload,
              });
            return api.createBucket({
              params: { save: save, reassign: this.reassign, offset: offset },
              ...payload,
            });
          })();

          if (data.url) {
            window.location.href = data.url;
            return;
          }

          this.warning = data.warning_message;
          if (offset === 0) {
            this.inList = data.in_list;
            this.outList = data.out_list;
            this.inListCount = data.in_list_count;
            this.outListCount = data.out_list_count;
          } else {
            this.inList.push(...data.in_list);
            this.outList.push(...data.out_list);
            this.inListCount += data.in_list_count;
            this.outListCount += data.out_list_count;
          }

          offset = data.next_offset;
        }
        this.loading = null;
      } catch (err) {
        this.warning = errorParser(err);
        this.loading = null;
      }
    },
  },
};
</script>

<style scoped></style>
