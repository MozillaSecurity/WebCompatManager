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
        @blur="onBlur"
        @keydown="onKeydown"
        @keyup="onKeyup"
        @click="onClick"
        @input="onInput"
      ></textarea>

      <div v-if="showSuggestions" class="suggestions" @mousedown.prevent>
        <template v-for="group in suggestions.groups" :key="group.name">
          <div class="suggestions-group">{{ group.name }}</div>
          <div
            v-for="option in group.opts"
            :key="'o' + option.idx"
            class="suggestions-option"
            :class="{ active: option.idx === activeIdx }"
            @mouseenter="activeIdx = option.idx"
            @click="accept(option, option.type !== 'op')"
          >
            <span v-if="option.badge" class="badge-code">{{
              option.badge
            }}</span>
            <span
              class="suggestion-label"
              :class="{ op: option.type === 'op' }"
              >{{ option.display }}</span
            >
          </div>
        </template>
      </div>
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
import { buildSuggestions, acceptSuggestion } from "../../bucket_filter";

export default {
  name: "FilterBar",
  props: {
    queryStr: { type: String, default: "" },
    countries: { type: Array, default: () => [] },
    labels: { type: Array, default: () => [] },
    error: { type: String, default: "" },
    disabled: { type: Boolean, default: false },
  },
  emits: ["query-input", "filter-change", "show-advanced"],
  data() {
    return { caret: 0, open: false, activeIdx: 0 };
  },
  computed: {
    suggestions() {
      return buildSuggestions(this.queryStr, this.caret, {
        countries: this.countries,
        labels: this.labels,
      });
    },
    // The suggestions list is shown only while the user is typing a term: there
    // must be a non-empty fragment under the caret. Focusing/clicking an empty
    // field or sitting in whitespace keeps it closed.
    showSuggestions() {
      return (
        this.open &&
        this.suggestions.frag !== "" &&
        this.suggestions.items.length > 0
      );
    },
  },
  methods: {
    // Local text update only — drives autocomplete, does not
    // refetch. The list is refetched on Enter (submitQuery) instead.
    emitQuery(value) {
      this.$emit("query-input", value);
    },
    // Run the query against the server (Enter while suggestions are closed, or
    // right after accepting a complete term). Defaults to the current prop, but
    // callers can pass the just-accepted value to avoid waiting on the prop
    // round-trip from the parent.
    submitQuery(queryStr = this.queryStr) {
      this.$emit("filter-change", { queryStr });
    },
    accept(sug, thenSearch = false) {
      const result = acceptSuggestion(
        this.queryStr,
        this.caret,
        this.suggestions,
        sug,
      );
      this.emitQuery(result.queryStr);
      this.activeIdx = 0;
      this.$nextTick(() => {
        const el = this.$refs.inputEl;
        if (el) {
          el.focus();
          el.setSelectionRange(result.caret, result.caret);
        }
        this.caret = result.caret;
        this.open = false;
        // Accepting a complete term (not an operator) runs the search right
        // away, using the just-accepted value rather than the (possibly not yet
        // round-tripped) prop.
        if (thenSearch) {
          this.submitQuery(result.queryStr);
        }
      });
    },
    onInput(e) {
      this.caret = e.target.selectionStart;
      this.open = true;
      this.activeIdx = 0;
      this.emitQuery(e.target.value);
    },
    onClick(e) {
      this.caret = e.target.selectionStart;
      this.open = true;
    },
    onKeyup(e) {
      if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) {
        this.caret = e.target.selectionStart;
        this.open = true;
      }
    },
    onBlur() {
      setTimeout(() => {
        this.open = false;
      }, 160);
    },
    onKeydown(e) {
      const { items } = this.suggestions;
      const listOpen = this.showSuggestions;

      // Enter: accept the highlighted suggestion only when the list is
      // offering a completion. If the term under the caret is already
      // complete (exactMatch — e.g. a fully-typed "country:GB"), accepting
      // would just re-insert it, so submit the query instead.
      // Accepting a complete term (a value, not an AND/OR/NOT operator) also
      // runs the search immediately; accepting an operator does not, since the
      // query clearly isn't finished and the user is still building it.
      if (e.key === "Enter") {
        e.preventDefault();
        if (listOpen && !this.suggestions.exactMatch) {
          const sug = items[this.activeIdx] || items[0];
          this.accept(sug, sug.type !== "op");
        } else {
          this.open = false;
          this.submitQuery();
        }
        return;
      }

      if (!listOpen) {
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        this.activeIdx = (this.activeIdx + 1) % items.length;
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        this.activeIdx = (this.activeIdx - 1 + items.length) % items.length;
      } else if (e.key === "Tab") {
        e.preventDefault();
        this.accept(items[this.activeIdx] || items[0]);
      } else if (e.key === "Escape") {
        this.open = false;
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
.suggestions {
  position: absolute;
  z-index: 55;
  top: calc(100% + 5px);
  left: 0;
  right: 0;
  background: #fff;
  border: 1px solid #ccc;
  border-radius: 6px;
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.14);
  overflow: hidden;
  max-height: 300px;
  overflow-y: auto;
}
.suggestions-group {
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #999;
  padding: 8px 12px 4px;
  font-weight: 700;
}
.suggestions-option {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 7px 12px;
  cursor: pointer;
}
.suggestions-option.active {
  background: #0969da;
  color: #fff;
}
.suggestions-option .badge-code {
  flex: none;
  box-sizing: border-box;
  min-width: 30px;
  text-align: center;
  font-size: 11px;
  font-weight: 700;
  color: #666;
  border: 1px solid #ccc;
  border-radius: 3px;
  padding: 0 5px;
}
.suggestions-option.active .badge-code {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.6);
}
.suggestion-label.op {
  color: #8250df;
  font-weight: 700;
}
.suggestions-option.active .suggestion-label {
  color: #fff;
}

.advanced-link {
  margin-top: 9px;
}
</style>
