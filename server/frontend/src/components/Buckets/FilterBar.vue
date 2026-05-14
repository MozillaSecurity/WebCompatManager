<template>
  <div>
    <div class="btn-group" role="group" aria-label="Bucket status filter">
      <button
        v-for="tab in bucketStates"
        :key="tab.key"
        type="button"
        :class="[
          'btn',
          activeState === tab.key ? 'btn-primary' : 'btn-default',
        ]"
        :disabled="disabled"
        @click="setStatus(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <div class="filter-row">
      <div class="input-group input-group-sm domain-input">
        <span class="input-group-addon"><i class="bi bi-globe2"></i></span>
        <input
          ref="domainInput"
          :value="domainFilter"
          type="text"
          class="form-control"
          placeholder="Domain filter…"
          :disabled="disabled"
          @change="onDomainChange"
          @keyup.enter="onDomainChange"
        />
        <span class="input-group-btn">
          <button
            class="btn btn-default btn-sm"
            type="button"
            :disabled="disabled"
            @click="onDomainSearch"
          >
            <i class="bi bi-search"></i>
          </button>
          <button
            v-if="domainFilter"
            class="btn btn-default btn-sm"
            type="button"
            @click="$emit('filter-change', { domainFilter: '' })"
          >
            ✕
          </button>
        </span>
      </div>

      <template v-for="filter in visibleFilters" :key="filter.key">
        <select
          v-if="filter.type === 'single'"
          :value="triageStatus"
          class="form-control input-sm"
          style="width: auto"
          :data-filter="filter.key"
          :disabled="disabled"
          @change="onFilterChange(filter, $event.target.value || null)"
        >
          <option value="">Any {{ filter.label }}</option>
          <option
            v-for="opt in filter.options"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </option>
        </select>
      </template>
    </div>
    <a class="advanced-link text-muted" @click="$emit('show-advanced')"
      >Switch to advance mode ›</a
    >
  </div>
</template>

<script>
import { BUCKET_STATES } from "../../filter_helpers";

export const FILTERS = [
  {
    key: "triageStatus",
    label: "Triage Status",
    queryField: "triage_status",
    type: "single",
    visibleWhen: "triaged",
  },
];

export default {
  name: "FilterBar",
  props: {
    activeState: { type: String, required: true },
    domainFilter: { type: String, default: "" },
    triageStatus: { type: String, default: null },
    triageStatusOptions: { type: Array, default: () => [] },
    disabled: { type: Boolean, default: false },
  },
  emits: ["filter-change", "show-advanced"],
  computed: {
    bucketStates() {
      return BUCKET_STATES;
    },
    visibleFilters() {
      return FILTERS.filter(
        (f) => !f.visibleWhen || f.visibleWhen === this.activeState,
      ).map((f) => ({
        ...f,
        options:
          f.key === "triageStatus"
            ? this.triageStatusOptions
            : (f.options ?? []),
      }));
    },
  },
  methods: {
    setStatus(status) {
      const update = { activeState: status };
      if (status !== "triaged") update.triageStatus = null;
      this.$emit("filter-change", update);
    },
    onDomainChange(e) {
      this.$emit("filter-change", { domainFilter: e.target.value });
    },
    onDomainSearch() {
      this.$emit("filter-change", {
        domainFilter: this.$refs.domainInput.value,
      });
    },
    onFilterChange(filter, value) {
      this.$emit("filter-change", { [filter.key]: value });
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
.domain-input {
  width: 260px;
}
.advanced-link {
  margin-left: auto;
  font-size: 11px;
  cursor: pointer;
}
</style>
