<template>
  <tr v-on:click="report.view_url">
    <td class="wrap-normal">{{ report.reported_at | date }}</td>
    <td class="wrap-anywhere">
      <span class="two-line-limit">{{ report.url }}</span>
    </td>
    <td class="wrap-normal">{{ report.comments }}</td>
    <td>
      <img
        v-if="report.os === 'Linux'"
        width="16px"
        height="16px"
        alt="Linux"
        :src="staticLogo('linux')"
      />
      <img
        v-else-if="report.os === 'Mac'"
        width="16px"
        height="16px"
        alt="macOS"
        :src="staticLogo('macosx')"
      />
      <img
        v-else-if="report.os === 'Windows'"
        width="16px"
        height="16px"
        alt="Windows"
        :src="staticLogo('windows')"
      />
      <img
        v-else-if="report.os === 'Android'"
        width="16px"
        height="16px"
        alt="Android"
        :src="staticLogo('android')"
      />
      <span v-else>{{ report.os }}</span>
    </td>
    <td>{{ report.app_name }}</td>
    <td>{{ report.app_channel }}</td>
    <td>{{ report.app_version }}</td>
    <td>{{ report.breakage_category }}</td>
    <td>
      {{
        report.details.boolean
          .broken_site_report_tab_info_antitracking_has_tracking_content_blocked
      }}
    </td>
    <td>
      {{
        report.details.string
          .broken_site_report_tab_info_antitracking_block_list
      }}
    </td>
    <td>
      {{
        report.details.boolean
          .broken_site_report_tab_info_antitracking_is_private_browsing
      }}
    </td>
  </tr>
</template>

<script>
import { date } from "../../helpers";

export default {
  props: {
    report: {
      type: Object,
      required: true,
    },
  },
  filters: {
    date: date,
  },
  methods: {
    staticLogo(name) {
      return window.location.origin + "/static/img/os/" + name + ".png";
    },
  },
};
</script>
