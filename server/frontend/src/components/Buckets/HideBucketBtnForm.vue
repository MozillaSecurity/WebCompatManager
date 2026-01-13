<template>
  <div>
    <p>
      This will hide the bucket from the default view for the specified number
      of weeks.
    </p>
    <p>
      Incoming reports matching the signature will still be put in this bucket.
    </p>
    <div class="table">
      <div class="tr">
        <label class="td" for="weeks">Weeks</label>
        <input
          id="id_weeks"
          v-model="selectedTime"
          class="td"
          type="number"
          min="1"
          max="12"
          @change="$emit('update-time', selectedTime)"
        />
      </div>
    </div>
  </div>
</template>

<script>
import { onMounted, ref } from "vue";

export default {
  setup(props, context) {
    const selectedTime = ref(1);

    onMounted(() => {
      context.emit("update-time", selectedTime.value);
    });

    return {
      selectedTime,
    };
  },
};
</script>

<style scoped>
p {
  text-align: left;
}
.table {
  display: table;
}
.tr {
  display: table-row;
  text-align: left;
}
.td {
  display: table-cell;
  padding: 8px;
}
</style>
