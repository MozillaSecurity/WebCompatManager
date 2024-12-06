<template>
  <nav aria-label="Page navigation">
    <ul class="pagination pagination-sm">
      <li :class="{ disabled: page === 1 }">
        <a
          aria-label="Previous page"
          class="bi bi-caret-left-fill"
          title="Previous page"
          v-on:click="prevPage"
        ></a>
      </li>
      <li v-if="showBegin">
        <a
          aria-label="Navigate to first page"
          title="First page"
          v-on:click="gotoPage(1)"
          >…</a
        >
      </li>
      <li :class="{ active: page === pn }" :key="pn" v-for="pn in pagesShown">
        <a
          :aria-label="`Navigate to page ${pn}`"
          :title="`Page ${pn}`"
          v-on:click="gotoPage(pn)"
          >{{ pn }}</a
        >
      </li>
      <li v-if="showEnd">
        <a
          aria-label="Navigate to last page"
          title="Last page"
          v-on:click="gotoPage(pages)"
          >…</a
        >
      </li>
      <li :class="{ disabled: page === pages }">
        <a
          aria-label="Next page"
          class="bi bi-caret-right-fill"
          title="Next page"
          v-on:click="nextPage"
        ></a>
      </li>
    </ul>
  </nav>
</template>

<script>
import _range from "lodash/range";

export default {
  props: {
    initial: {
      type: Number,
      default: 1,
    },
    pages: {
      type: Number,
      required: true,
    },
    show: {
      type: Number,
      default: 3,
    },
  },
  data: function () {
    return {
      page: this.initial,
      pagesShown: [],
      showBegin: false,
      showEnd: false,
    };
  },
  methods: {
    gotoPage: function (pn) {
      if (pn >= 1 && pn <= this.pages && pn !== this.page) {
        this.page = pn;
        this.$emit("page-changed", this.page);
      }
    },
    nextPage: function () {
      if (this.page < this.pages) {
        this.page++;
        this.$emit("page-changed", this.page);
      }
    },
    prevPage: function () {
      if (this.page > 1) {
        this.page--;
        this.$emit("page-changed", this.page);
      }
    },
    recalculate: function () {
      if (this.page > this.show && this.page <= this.pages - this.show) {
        const range = Math.max(Math.floor(this.show / 2), 1);
        this.pagesShown = _range(this.page - range, this.page + range + 1);
        this.showBegin = true;
        this.showEnd = true;
      } else if (this.page <= this.show) {
        this.pagesShown = _range(1, Math.min(this.show + 1, this.pages) + 1);
        this.showBegin = false;
        this.showEnd = this.pages > this.show + 1;
      } else {
        this.pagesShown = _range(this.pages - this.show, this.pages + 1);
        this.showBegin = true;
        this.showEnd = false;
      }
    },
  },
  watch: {
    page() {
      this.recalculate();
    },
    pages() {
      this.recalculate();
    },
  },
  mounted: function () {
    this.recalculate();
  },
};
</script>

<style scoped>
nav {
  display: inline-block;
  vertical-align: middle;
}
ul {
  display: inline;
}
</style>
