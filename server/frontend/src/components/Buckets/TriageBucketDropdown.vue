<template>
  <div class="triage-bucket-dropdown">
    <a class="btn btn-default" data-testid="triage-trigger" @click="showPanel">
      {{ currentStatus ? "Change triage status" : "Mark triaged" }}
    </a>

    <div v-if="isPanelVisible" class="triage-panel" data-testid="triage-panel">
      <div class="panel-header">Select status</div>
      <div class="panel-options">
        <a
          v-for="choice in choices"
          :key="choice.value"
          class="panel-option"
          :class="{ 'panel-option--selected': choice.value === currentStatus }"
          :data-testid="`triage-option-${choice.value}`"
          @click="choice.value !== currentStatus && selectStatus(choice.value)"
        >
          <span class="option-rail"></span>
          <span class="option-label">{{ choice.label }}</span>
          <span v-if="choice.value === currentStatus" class="option-check"
            >✓</span
          >
        </a>
      </div>
      <div v-if="currentStatus" class="panel-danger-zone">
        <a
          class="panel-option panel-option--unmark"
          data-testid="triage-unmark"
          @click="selectStatus(null)"
        >
          <span class="option-rail"></span>
          <span class="option-label">Unmark triaged</span>
        </a>
      </div>
      <div class="panel-footer">
        <a class="panel-cancel" @click="hidePanel">Cancel</a>
      </div>
    </div>

    <div v-if="isPanelVisible" class="panel-backdrop" @click="hidePanel"></div>
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
  data() {
    return {
      isPanelVisible: false,
    };
  },
  methods: {
    showPanel() {
      this.isPanelVisible = true;
    },
    hidePanel() {
      this.isPanelVisible = false;
    },
    selectStatus(status) {
      this.isPanelVisible = false;
      this.$emit("update", status);
    },
  },
};
</script>

<style scoped>
.triage-bucket-dropdown {
  display: inline-block;
  position: relative;
}

.triage-panel {
  position: absolute;
  top: calc(100% + 5px);
  left: 0;
  background: #fff;
  border: 1px solid #ccc;
  border-radius: 5px;
  z-index: 1000;
  min-width: 210px;
  overflow: hidden;
}

.panel-header {
  background: #fafafa;
  padding: 9px 14px 8px;
  border-bottom: 1px solid #eee;
  font-weight: bold;
}

.panel-options {
  padding: 4px 0;
}

.panel-option {
  display: flex;
  align-items: center;
  padding: 0;
  cursor: pointer;
  color: #333;
  text-decoration: none;
}

.panel-option:hover {
  background-color: #f7f7f7;
  text-decoration: none;
  color: #333;
}

.option-rail {
  display: block;
  width: 3px;
  align-self: stretch;
  background-color: transparent;
  flex-shrink: 0;
  border-radius: 0 2px 2px 0;
}

.panel-option:hover .option-rail {
  background-color: #ccc;
}

.panel-option--selected .option-rail {
  background-color: #0066cc;
}

.option-label {
  flex: 1;
  padding: 8px 12px 8px 10px;
  font-size: 13px;
  line-height: 1.3;
}

.option-check {
  padding-right: 12px;
  font-size: 11px;
  color: #0066cc;
  font-weight: 700;
}

.panel-option--selected {
  background-color: #f0f6ff;
  cursor: default;
  pointer-events: none;
}

.panel-option--selected .option-label {
  color: #0055aa;
  font-weight: 600;
}

.panel-danger-zone {
  border-top: 1px solid #eee;
}

.panel-option--unmark .option-label {
  color: #c0392b;
}

.panel-option--unmark:hover {
  background-color: #fdf4f3;
}

.panel-option--unmark:hover .option-rail {
  background-color: #c0392b;
}

.panel-option--unmark:hover .option-label {
  color: #a93226;
}

.panel-footer {
  padding: 7px 14px;
  border-top: 1px solid #eee;
  text-align: right;
  background: #fafafa;
}

.panel-cancel {
  color: #999;
  cursor: pointer;
  text-decoration: none;
}

.panel-cancel:hover {
  color: #555;
  text-decoration: none;
}

.panel-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 999;
}
</style>
