<template>
  <a class="btn btn-default" @click="link">Mark triaged</a>
</template>

<script>
import swal from "sweetalert";
import { h, ref, render } from "vue";
import { errorParser, hideBucketUntil } from "../../helpers";
import HideBucketBtnForm from "./HideBucketBtnForm.vue";

export default {
  props: {
    bucket: {
      type: Number,
      default: null,
      required: true,
    },
  },
  methods: {
    async link() {
      const selectedTime = ref(null);
      const container = document.createElement("div");

      const formCtor = h(HideBucketBtnForm, {
        onUpdateTime: (time) => (selectedTime.value = time),
      });

      render(formCtor, container);

      const value = await swal({
        title: "Mark bucket triaged",
        content: container,
        buttons: true,
      });

      if (value) {
        try {
          const data = await hideBucketUntil(
            this.bucket,
            new Date(Date.now() + selectedTime.value * 7 * 24 * 60 * 60 * 1000),
          );
          window.location.href = data.url;
        } catch (err) {
          swal("Oops", errorParser(err), "error");
        }
      }
    },
  },
};
</script>
