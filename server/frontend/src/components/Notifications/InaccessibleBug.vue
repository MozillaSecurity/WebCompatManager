<template>
  <div class="row override-row">
    <small class="col-md-1">
      Received {{ notification.timestamp | date }}
    </small>
    <span class="label label-danger">Inaccessible bug</span>
    <span class="description">
      {{ notification.description }}
    </span>
    <button type="button" class="close" v-on:click="dismiss">
      <span aria-hidden="true" title="Dismiss">&times;</span>
    </button>
    <a
      class="btn btn-info pull-right"
      :href="notification.external_bug_url"
      target="_blank"
    >
      View external bug
    </a>
  </div>
</template>

<script>
import { date, errorParser } from "../../helpers";
import * as api from "../../api";

export default {
  props: {
    notification: {
      type: Object,
      required: true,
    },
  },
  filters: {
    date: date,
  },
  methods: {
    async dismiss() {
      try {
        await api.dismissNotification(this.notification.id);
        this.$emit("remove-notification", this.notification.id);
      } catch (err) {
        this.$emit(
          "update-dismiss-error",
          `An error occurred while marking notification ${
            this.notification.id
          } as read: ${errorParser(err)}`,
        );
      }
    },
  },
};
</script>

<style scoped>
.override-row {
  margin-left: 1.5rem;
  margin-right: 1.5rem;
}
.description {
  margin-left: 1.5rem;
  margin-right: 1.5rem;
}
button.close {
  margin-left: 3rem;
}
small {
  padding-left: 0rem;
  padding-right: 0rem;
  margin-right: 1rem;
}
</style>
