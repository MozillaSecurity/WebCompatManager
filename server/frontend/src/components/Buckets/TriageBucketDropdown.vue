<template>
  <div class="btn-group">
    <a
      class="btn btn-default dropdown-toggle"
      data-toggle="dropdown"
      href="#"
      role="button"
      data-testid="triage-trigger"
    >
      {{ currentStatus ? "Change triage status" : "Mark triaged" }}
      <span class="caret"></span>
    </a>
    <ul class="dropdown-menu" data-testid="triage-panel">
      <li
        v-for="choice in choices"
        :key="choice.value"
        :class="{ active: choice.value === currentStatus }"
      >
        <a
          href="#"
          :data-testid="`triage-option-${choice.value}`"
          @click.prevent="
            choice.value !== currentStatus && selectStatus(choice.value)
          "
        >
          {{ choice.label }}
        </a>
      </li>
      <li v-if="currentStatus" class="divider" role="presentation"></li>
      <li v-if="currentStatus">
        <a
          href="#"
          class="text-danger"
          data-testid="triage-unmark"
          @click.prevent="selectStatus(null)"
          >Unmark triaged</a
        >
      </li>
    </ul>
  </div>
</template>

<script>
export default {
  name: "TriageBucketDropdown",
  props: {
    bucketId: {
      type: Number,
      required: true,
    },
    currentStatus: {
      type: String,
      default: null,
    },
    choices: {
      type: Array,
      default: () => [],
    },
  },
  emits: ["update"],
  methods: {
    selectStatus(status) {
      this.$emit("update", status);
    },
  },
};
</script>
