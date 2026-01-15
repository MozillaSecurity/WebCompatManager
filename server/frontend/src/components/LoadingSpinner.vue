<template>
  <div class="spinner-container">
    <div class="spinner" :style="spinnerStyle"></div>
  </div>
</template>

<script>
export default {
  name: "LoadingSpinner",
  props: {
    color: {
      type: String,
      default: "#5dc596",
    },
    size: {
      type: String,
      default: "35px",
    },
  },
  computed: {
    spinnerStyle() {
      return {
        width: this.size,
        height: this.size,
        borderColor: `${this.color} transparent transparent transparent`,
        borderWidth: '2px',
      };
    },
  },
};
</script>

<style scoped>
.spinner-container {
  text-align: center;
}

.spinner {
  display: inline-block;
  border: 4px solid;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
</style>
