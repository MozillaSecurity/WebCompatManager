<template>
  <div>
    <div class="wrap">
      <textarea
        ref="inputEl"
        class="form-control input"
        rows="1"
        spellcheck="false"
        autocapitalize="off"
        autocomplete="off"
        placeholder="Type label, country or domain name"
        data-testid="query-input"
        :value="queryStr"
        :disabled="disabled"
        @keydown="onKeydown"
        @input="onInput"
      ></textarea>
    </div>
    <div v-if="error" class="help-block text-danger" data-testid="query-error">
      <i class="bi bi-exclamation-triangle"></i> {{ error }}
    </div>
    <button
      type="button"
      class="btn btn-link btn-xs advanced-link"
      @click="$emit('show-advanced')"
    >
      Switch to advance mode ›
    </button>
  </div>
</template>

<script>
export default {
  name: "FilterBar",
  props: {
    queryStr: { type: String, default: "" },
    error: { type: String, default: "" },
    disabled: { type: Boolean, default: false },
  },
  emits: ["query-input", "filter-change", "show-advanced"],
  methods: {
    // Local text update only — does not refetch. The list is refetched on
    // Enter (submitQuery) instead.
    emitQuery(value) {
      this.$emit("query-input", value);
    },
    // Run the query against the server. Defaults to the current prop, but
    // callers can pass a value to avoid waiting on the prop round-trip from the
    // parent.
    submitQuery(queryStr = this.queryStr) {
      this.$emit("filter-change", { queryStr });
    },
    onInput(e) {
      this.emitQuery(e.target.value);
    },
    onKeydown(e) {
      if (e.key === "Enter") {
        e.preventDefault();
        this.submitQuery();
      }
    },
  },
};
</script>

<style scoped>
.wrap {
  position: relative;
  margin-top: 14px;
}

.input {
  height: auto;
  resize: none;
  overflow: hidden;
  white-space: pre-wrap;
  word-break: break-word;
}

.advanced-link {
  margin-top: 9px;
}
</style>
