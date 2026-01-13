<template>
  <tr v-on:click="report.view_url">
    <td class="wrap-normal">
      {{ formatShorterDate(report.reported_at) }}<br />
      (<a :href="report.view_url">Full details</a>)
    </td>
    <td class="url-col">
      <a :href="report.url" target="_blank" rel="noreferrer">
        {{ report.url }}
      </a>
    </td>
    <td class="wrap-normal comments-col">
      <div>
        <strong>{{ report.breakage_category ?? "unknown" }}</strong
        >: {{ maybeTranslatedComments(report) }}
      </div>
    </td>
    <td class="wrap-none ml-validity-col">
      <span :class="validityClass(report.ml_valid_probability)">
        {{ validityLabel(report.ml_valid_probability) }}
      </span>
      <br />
      <small
        >{{
          (validityProbability(report.ml_valid_probability) * 100).toFixed(1)
        }}%</small
      >
    </td>
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
      {{ report.app_name }}
      {{ report.app_version }}
      ({{ report.app_channel }})
    </td>
    <td>
      PBM:
      {{
        humanBool(
          report.details.boolean
            ?.broken_site_report_tab_info_antitracking_is_private_browsing
        )
      }}<br />

      Blocklist:
      {{
        report.details.string
          ?.broken_site_report_tab_info_antitracking_block_list || "n/a"
      }}<br />

      Any content blocked:
      {{
        humanBool(
          report.details.boolean
            ?.broken_site_report_tab_info_antitracking_has_tracking_content_blocked
        )
      }}
    </td>
  </tr>
</template>

<script>
import { shorterDate } from "../../helpers";

export default {
  props: {
    report: {
      type: Object,
      required: true,
    },
  },
  methods: {
    formatShorterDate: shorterDate,
    humanBool(value) {
      if (value === undefined || value === null) {
        return "n/a";
      }
      return value ? "yes" : "no";
    },
    staticLogo(name) {
      return window.location.origin + "/static/img/os/" + name + ".png";
    },
    maybeTranslatedComments(report) {
      if (
        report.comments_original_language &&
        report.comments_original_language !== "en"
      ) {
        // The translation pipeline does escape HTML, and the "easiest" way to
        // un-escape that is by just assignign it to an element and letting
        // the browser do the magic.. :/
        let el = document.createElement("span");
        el.innerHTML = `[${report.comments_original_language}] ${report.comments_translated}`;
        return el.innerText;
      }

      return report.comments;
    },
    validityLabel(mlValidProbability) {
      if (!mlValidProbability) {
        return "Unknown";
      }

      return mlValidProbability >= 0.5 ? "Valid" : "Invalid";
    },
    validityProbability(mlValidProbability) {
      if (!mlValidProbability) {
        return 0;
      }

      return mlValidProbability >= 0.5
        ? mlValidProbability
        : 1 - mlValidProbability;
    },
    validityClass(mlValidProbability) {
      if (!mlValidProbability) {
        return "validity-unknown";
      }

      return mlValidProbability >= 0.5 ? "validity-valid" : "validity-invalid";
    },
  },
};
</script>

<style scoped>
.comments-col {
  overflow-wrap: anywhere;

  div {
    max-height: 150px;
    overflow: scroll;
  }
}

.url-col a {
  display: block;
  max-width: 300px;
  overflow: scroll;
  text-overflow: ellipsis;

  /*
   * This is to ensure the overlay scrollbar isn't overlaying the text. Ideally,
   * this link would be `height: 100%`, but bug 1598458 is a thing.
   */
  padding-bottom: 1.2em;
}

.ml-validity-col {
  text-align: center;
}

.validity-valid {
  color: #28a745;
  font-weight: bold;
}

.validity-invalid {
  color: #dc3545;
  font-weight: bold;
}

.validity-unknown {
  color: #6c757d;
  font-style: italic;
}
</style>
