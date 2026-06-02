/**
 * Used here only to un-indent multi-line strings, because I refuse to have
 * the description templates strings in here with weird indentations.
 */
function trimStartAll(input) {
  return input
    .split("\n")
    .map((l) => l.trimStart())
    .join("\n");
}

/**
 * Builds the default URLSearchParams used to file a new bug and returns it so
 * it can be extended.
 */
export function newBugDefaultParams(report) {
  return new URLSearchParams([
    ["bug_file_loc", report.url],
    ["keywords", "webcompat:site-report"],
    ["op_sys", `${report.os}`],
    ["product", "Web Compatibility"],
    ["rep_platform", "Desktop"],
    ["short_desc", `${new URL(report.url).hostname} - CHANGE_ME`],
    ["status_whiteboard", "[webcompat-source:product]"],
    ["version", `Firefox ${report.app_major_version}`],
  ]);
}

/**
 * Opens a new tab/window to Bugzilla with a prefilled bug form
 */
export function openPrefilledBugzillaBug(searchParams) {
  const url = new URL("https://bugzilla.mozilla.org/enter_bug.cgi");
  url.search = searchParams.toString();
  window.open(url.toString(), "_blank");
}

/**
 * Generates a pre-filled Bugzilla comment for a Site Report issue
 */
export function siteReportDescription(report) {
  return trimStartAll(`**Environment:**
    Operating system: ${report.os}
    Firefox version: ${report.app_name} ${report.app_version} (${report.app_channel})

    **Preconditions:**
    - Clean profile

    **Steps to reproduce:**
    1. Navigate to: ${report.url}
    2. Step 2

    **Expected Behavior:**
    text

    **Actual Behavior:**
    text

    **Notes:**
    - Reproducible on the latest Firefox Release and Nightly
    - Reproducible regardless of the ETP setting
    - Works as expected using Chrome

    ---

    Created from webcompat-user-report:${report.uuid}`);
}

/**
 * Generates a pre-filled Bugzilla comment for a ETP Strict compat issue
 */
export function etpStrictReportDescription(report) {
  return trimStartAll(`**Environment:**
    Operating system: ${report.os}
    Firefox version: ${report.app_name} ${report.app_version} (${report.app_channel})

    **Preconditions:**
    - ETP set to Standard in Private Browsing Mode

    **Steps to reproduce:**
    1. Navigate to: ${report.url}
    2. Step 2

    **Expected Behavior:**
    text

    **Actual Behavior:**
    text

    **Notes:**
    - Reproduces in ETP Strict (Normal mode) and ETP Standard (Private Browsing mode)
    - Reproduces in firefox-nightly, and firefox-release
    - Does not reproduce in chrome

    ---

    Created from webcompat-user-report:${report.uuid}`);
}
