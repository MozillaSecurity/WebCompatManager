<template>
  <div>
    <div class="query-editor-header">
      <a role="button" @click="$emit('close')">← Back to basic mode</a>&nbsp;
      <span class="text-muted"
        >(IMPORTANT: any changes in this field will be erased)</span
      >
    </div>
    <label for="id_query">Search Query</label>
    <HelpJSONQueryPopover
      :parameters="[
        { name: 'id', type: 'Integer (ID)' },
        { name: 'bug', type: 'Integer (ID)' },
        { name: 'bug__closed', type: 'Date' },
        { name: 'bug__external_id', type: 'String' },
        { name: 'bug__external_type', type: 'Integer (ID)' },
        { name: 'bug__external_type__classname', type: 'String' },
        { name: 'bug__external_type__hostname', type: 'String' },
        { name: 'description', type: 'String' },
        { name: 'domain', type: 'String' },
        { name: 'domain__endswith', type: 'String' },
        { name: 'domain__isnull', type: 'Boolean' },
        { name: 'priority', type: 'Integer' },
        { name: 'signature', type: 'String' },
        { name: 'size', type: 'Integer' },
        { name: 'triage_status', type: 'String' },
      ]"
    />
    <textarea
      id="id_query"
      :value="modelValue"
      class="form-control"
      name="query"
      spellcheck="false"
      :rows="(modelValue.match(/\n/g) || '').length + 1"
      @input="$emit('update:modelValue', $event.target.value)"
    ></textarea>
    <br v-if="error" />
    <div v-if="error" class="alert alert-warning" role="alert">
      {{ error }}
    </div>
    <br />
    <button :disabled="loading" @click="$emit('run')">Run query</button>
  </div>
</template>

<script>
import HelpJSONQueryPopover from "../HelpJSONQueryPopover.vue";

export default {
  name: "QueryEditor",
  components: { HelpJSONQueryPopover },
  props: {
    modelValue: { type: String, required: true },
    error: { type: String, default: "" },
    loading: { type: Boolean, default: false },
  },
  emits: ["update:modelValue", "run", "close"],
};
</script>

<style scoped>
.query-editor-header {
  margin-bottom: 8px;
}
</style>
