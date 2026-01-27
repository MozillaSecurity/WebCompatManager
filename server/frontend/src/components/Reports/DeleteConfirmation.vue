<template>
  <table>
    <thead>
      <tr>
        <th>Reports Affected</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>{{ reportCount }}</td>
      </tr>
    </tbody>
  </table>
</template>

<script>
export default {
  props: {
    reportCount: {
      type: Number,
      required: true,
    },
  },
};
</script>

<style scoped>
table {
  margin: 0 auto;
}
th,
td {
  padding: 8px;
}
</style>
