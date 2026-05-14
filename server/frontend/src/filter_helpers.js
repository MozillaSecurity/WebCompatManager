export const BUCKET_STATES = [
  { key: "all", label: "All", queryFields: () => ({}) },
  {
    key: "needs_triage",
    label: "Needs Triage",
    queryFields: () => ({ bug__isnull: true, triage_status__isnull: true }),
  },
  {
    key: "logged",
    label: "Logged",
    queryFields: () => ({ bug__isnull: false }),
  },
  {
    key: "triaged",
    label: "Triaged",
    queryFields: ({ triageStatus }) =>
      triageStatus
        ? { triage_status: triageStatus }
        : { triage_status__isnull: false },
  },
];

export const buildQuery = ({ activeState, domainFilter, triageStatus }) => {
  const tab = BUCKET_STATES.find((t) => t.key === activeState);
  let query = { op: "AND", ...tab?.queryFields({ triageStatus }) };

  const domain = domainFilter?.trim() ?? "";
  if (domain) {
    query = {
      op: "AND",
      0: query,
      1: {
        op: "AND",
        0: { op: "OR", domain, domain__endswith: "." + domain },
        domain__isnull: false,
      },
    };
  }

  return JSON.stringify(query, null, 2);
};
