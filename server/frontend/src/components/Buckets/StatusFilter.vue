<template>
  <div>
    <div class="btn-group" role="group" aria-label="Bucket status filter">
      <button
        v-for="key in stateKeys"
        :key="key"
        type="button"
        :class="['btn', activeState === key ? 'btn-primary' : 'btn-default']"
        :disabled="disabled"
        :data-testid="key"
        @click="setStatus(key)"
      >
        {{ states[key].label }}
      </button>
    </div>

    <div v-if="activeState === 'triaged'" class="filter-row">
      <select
        :value="triageStatus"
        class="form-control input-sm"
        style="width: auto"
        data-filter="triageStatus"
        data-testid="triage-status"
        :disabled="disabled"
        @change="
          $emit('filter-change', { triageStatus: $event.target.value || null })
        "
      >
        <option value="">Any Triage Status</option>
        <option
          v-for="opt in triageStatusOptions"
          :key="opt.value"
          :value="opt.value"
        >
          {{ opt.label }}
        </option>
      </select>
    </div>
  </div>
</template>

<script>
import { BUCKET_STATES } from "../../bucket_filter_config";

export default {
  name: "StatusFilter",
  props: {
    activeState: { type: String, required: true },
    triageStatus: { type: String, default: null },
    triageStatusOptions: { type: Array, default: () => [] },
    disabled: { type: Boolean, default: false },
  },
  emits: ["filter-change"],
  computed: {
    states() {
      return BUCKET_STATES;
    },
    stateKeys() {
      return Object.keys(BUCKET_STATES);
    },
  },
  methods: {
    setStatus(status) {
      const update = { activeState: status };
      if (status !== "triaged") {
        update.triageStatus = null;
      }
      this.$emit("filter-change", update);
    },
  },
};
</script>

<style scoped>
.filter-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
</style>
