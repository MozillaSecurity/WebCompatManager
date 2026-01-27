<template>
  <div class="table-responsive">
    <table class="table table-condensed table-hover table-bordered table-db">
      <thead>
        <tr>
          <th>Reported</th>
          <th>UUID</th>
          <th>URL</th>
          <th>App</th>
          <th>Channel</th>
          <th>Version</th>
          <th>Breakage Category</th>
          <th>OS</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(entry, index) in entries"
          :key="entry.id"
          :class="{ odd: index % 2 === 0, even: index % 2 !== 0 }"
        >
          <td>{{ formatDate(entry.reported_at) }}</td>
          <td>
            <a :href="entry.view_url">{{ entry.uuid }}</a>
          </td>
          <td>{{ entry.url }}</td>
          <td>{{ entry.app_name }}</td>
          <td>{{ entry.app_channel }}</td>
          <td>{{ entry.app_version }}</td>
          <td>{{ entry.breakage_category }}</td>
          <td>
            <img
              v-if="entry.os === 'Linux'"
              width="16px"
              height="16px"
              alt="Linux"
              :src="staticLogo('linux')"
            />
            <img
              v-else-if="entry.os === 'Mac'"
              width="16px"
              height="16px"
              alt="macOS"
              :src="staticLogo('macosx')"
            />
            <img
              v-else-if="entry.os === 'Windows'"
              width="16px"
              height="16px"
              alt="Windows"
              :src="staticLogo('windows')"
            />
            <img
              v-else-if="entry.os === 'Android'"
              width="16px"
              height="16px"
              alt="Android"
              :src="staticLogo('android')"
            />
            <template v-else>{{ entry.os }}</template>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
import { date } from "../../../helpers";

export default {
  props: {
    entries: {
      type: Array,
      required: true,
    },
  },
  methods: {
    formatDate: date,
    staticLogo(name) {
      return window.location.origin + "/static/img/os/" + name + ".png";
    },
  },
};
</script>

<style scoped></style>
