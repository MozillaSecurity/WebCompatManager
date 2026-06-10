class BucketFilter {
  constructor(key, label) {
    this.key = key;
    this.label = label;
  }

  suggest() {
    return [];
  }

  toQuery() {
    throw new Error(`${this.key} must implement toQuery()`);
  }
}

class CountryBucketFilter extends BucketFilter {
  constructor() {
    super("country", "Country");
  }

  suggest(fragment, options) {
    const q = fragment.toLowerCase();

    return (options.countries ?? [])
      .filter(
        (c) =>
          c.code.toLowerCase().includes(q) || c.name.toLowerCase().includes(q),
      )
      .map((c) => ({
        value: c.code,
        display: c.name,
        badge: c.code,
        key: this.key,
      }));
  }

  toQuery(value) {
    return { op: "AND", reportentry__country: value };
  }
}

class LabelBucketFilter extends BucketFilter {
  constructor() {
    super("label", "Label");
  }

  suggest(fragment, options) {
    const q = fragment.toLowerCase();

    return (options.labels ?? [])
      .filter((l) => l.name.toLowerCase().includes(q))
      .map((l) => ({ value: l.name, display: l.name, key: this.key }));
  }

  toQuery(value) {
    return { op: "AND", labels__label__name: value };
  }
}

class DomainBucketFilter extends BucketFilter {
  constructor() {
    super("domain", "Domain");
  }

  suggest(fragment) {
    return fragment
      ? [{ value: fragment, display: `domain: ${fragment}`, key: this.key }]
      : [];
  }

  toQuery(value) {
    return {
      op: "OR",
      domain: value,
      domain__endswith: `.${value}`,
    };
  }
}

class BucketState {
  constructor(key, label) {
    this.key = key;
    this.label = label;
  }

  queryFields() {
    throw new Error(`${this.key} must implement queryFields()`);
  }
}

class AllBucketState extends BucketState {
  constructor() {
    super("all", "All");
  }

  queryFields() {
    return {};
  }
}

class NeedsTriageBucketState extends BucketState {
  constructor() {
    super("needs_triage", "Needs Triage");
  }

  queryFields() {
    return { bug__isnull: true, triage_status__isnull: true };
  }
}

class HasBugBucketState extends BucketState {
  constructor() {
    super("has_bug", "Has a bug");
  }

  queryFields() {
    return { bug__isnull: false };
  }
}

class TriagedBucketState extends BucketState {
  constructor() {
    super("triaged", "Triaged");
  }

  queryFields({ triageStatus } = {}) {
    return triageStatus
      ? { triage_status: triageStatus }
      : { triage_status__isnull: false };
  }
}

const bucketFilterList = [
  new CountryBucketFilter(),
  new LabelBucketFilter(),
  new DomainBucketFilter(),
];

const bucketStateList = [
  new AllBucketState(),
  new NeedsTriageBucketState(),
  new HasBugBucketState(),
  new TriagedBucketState(),
];

export const BUCKET_FILTERS = Object.fromEntries(
  bucketFilterList.map((filter) => [filter.key, filter]),
);

export const BUCKET_STATES = Object.fromEntries(
  bucketStateList.map((state) => [state.key, state]),
);
