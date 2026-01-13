<template>
  <tr>
    <td>
      <a title="View bucket" :href="bucket.view_url">
        {{ bucket.id }}
      </a>
    </td>
    <td class="wrap-anywhere">
      <span class="two-line-limit">{{ bucket.description }}</span>
    </td>
    <td>{{ bucket.priority }}</td>
    <td>
      <activitygraph :data="bucket.report_history" :range="activityRange" />
    </td>
    <td class="wrap-anywhere">{{ formatDate(bucket.latest_report) }}</td>
    <td>
      {{ bucket.size }}
      <span
        v-if="bucket.reassign_in_progress"
        class="bi bi-hourglass-split"
        data-toggle="tooltip"
        data-placement="top"
        title="Reports are currently being reassigned in this bucket"
      ></span>
    </td>
    <td>
      <a
        class="btn btn-default"
        title="View details and comments"
        :href="bucket.view_url"
      >
        View details and comments
      </a>
    </td>
  </tr>
</template>

<script>
import { date } from "../../helpers";
import ActivityGraph from "../ActivityGraph.vue";

export default {
  components: {
    activitygraph: ActivityGraph,
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
    providers: {
      type: Array,
      required: true,
    },
    bucket: {
      type: Object,
      required: true,
    },
  },
  methods: {
    formatDate: date,
    addFilter(key, value) {
      this.$emit("add-filter", key, value);
    },
  },
};
</script>

<style scoped></style>
