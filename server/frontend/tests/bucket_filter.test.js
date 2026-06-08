import {
  validateQL,
  queryStrToJson,
  buildSuggestions,
  acceptSuggestion,
  buildQuery,
  buildBucketHash,
} from "../src/bucket_filter.js";
import { parseHash } from "../src/helpers.js";

describe("validateQL", () => {
  test("balanced is valid", () => {
    expect(validateQL("(domain:a OR domain:b)")).toEqual({
      valid: true,
      error: "",
    });
  });
  test("unbalanced paren invalid", () => {
    expect(validateQL("(domain:a").valid).toBe(false);
  });
});

describe("queryStrToJson", () => {
  test("domain term -> OR endswith form", () => {
    expect(queryStrToJson("domain:youtube.com")).toEqual({
      op: "OR",
      domain: "youtube.com",
      domain__endswith: ".youtube.com",
    });
  });
  test("country term -> reverse-relation lookup", () => {
    expect(queryStrToJson("country:GB")).toEqual({
      op: "AND",
      reportentry__country: "GB",
    });
  });
  test("label term -> reverse-relation lookup", () => {
    expect(queryStrToJson("label:nsfw")).toEqual({
      op: "AND",
      labels__label__name: "nsfw",
    });
  });
  test("NOT wraps the inner term", () => {
    expect(queryStrToJson("NOT country:GB")).toEqual({
      op: "NOT",
      0: { op: "AND", reportentry__country: "GB" },
    });
  });
  test("AND of two terms indexes children", () => {
    expect(queryStrToJson("country:GB AND domain:a")).toEqual({
      op: "AND",
      0: { op: "AND", reportentry__country: "GB" },
      1: { op: "OR", domain: "a", domain__endswith: ".a" },
    });
  });
  test("implicit AND between adjacent terms", () => {
    expect(queryStrToJson("domain:a country:GB")).toEqual({
      op: "AND",
      0: { op: "OR", domain: "a", domain__endswith: ".a" },
      1: { op: "AND", reportentry__country: "GB" },
    });
  });
  test("nested group -> nested JSON", () => {
    const json = queryStrToJson("domain:x AND (country:GB OR country:US)");
    expect(json.op).toBe("AND");
    expect(json[1].op).toBe("OR");
    expect(json[1][0]).toEqual({ op: "AND", reportentry__country: "GB" });
  });
  test("empty/whitespace query contributes nothing", () => {
    expect(queryStrToJson("")).toBeNull();
    expect(queryStrToJson("   ")).toBeNull();
  });
  test("unknown key is ignored", () => {
    expect(queryStrToJson("bogus:x")).toBeNull();
  });
  // liqe binds AND/OR left-to-right at equal precedence (NOT conventional
  // OR-lowest). Documented so the behavior is intentional, not accidental.
  test("mixed AND/OR without parens binds left-to-right (liqe)", () => {
    const json = queryStrToJson("country:GB OR domain:a AND domain:b");
    expect(json.op).toBe("AND");
  });
});

describe("buildSuggestions", () => {
  const opts = {
    countries: [{ code: "GB", name: "United Kingdom" }],
    labels: [{ name: "nsfw" }, { name: "worldcup2026" }],
  };
  test("explicit label: fragment suggests labels", () => {
    const menu = buildSuggestions("label:world", "label:world".length, opts);
    expect(menu.groups.map((g) => g.name)).toEqual(["Label"]);
    expect(menu.items.map((i) => i.value)).toEqual(["worldcup2026"]);
  });
  test("explicit country: fragment suggests countries", () => {
    const menu = buildSuggestions("country:g", "country:g".length, opts);
    expect(menu.groups[0].name).toBe("Country");
    expect(menu.items[0].value).toBe("GB");
  });
  test("bare fragment suggests across keys + no operators when first", () => {
    const menu = buildSuggestions("you", "you".length, opts);
    const names = menu.groups.map((g) => g.name);
    expect(names).toContain("Domain");
    expect(names).not.toContain("Operators");
  });
  test("operators appear once a term precedes the fragment", () => {
    const str = "domain:a ";
    const menu = buildSuggestions(str, str.length, opts);
    expect(menu.groups.map((g) => g.name)).toContain("Operators");
  });
  test("operator-like fragment after a term suggests only operators", () => {
    const str = "domain:a OR";
    const menu = buildSuggestions(str, str.length, opts);
    const names = menu.groups.map((g) => g.name);
    expect(names).toContain("Operators");
    expect(names).not.toContain("Domain");
    expect(names).not.toContain("Country");
  });
  test("operator-like fragment with no preceding term still suggests keys", () => {
    // No term before it, so "or" is just a value fragment, not an operator.
    const menu = buildSuggestions("or", "or".length, opts);
    const names = menu.groups.map((g) => g.name);
    expect(names).not.toContain("Operators");
  });
  test("a fully-typed term is flagged exactMatch", () => {
    // country:GB with GB available — accepting would re-insert it, so the
    // caller (FilterBar) treats Enter as "submit", not "accept".
    const menu = buildSuggestions("country:GB", "country:GB".length, opts);
    expect(menu.exactMatch).toBe(true);
  });
  test("a partial term is not exactMatch", () => {
    const menu = buildSuggestions("country:g", "country:g".length, opts);
    expect(menu.exactMatch).toBe(false);
  });

  test("fragStart and frag are read from the caret, not the whole string", () => {
    // caret sits right after "do" in "do country:GB" -> fragment is "do"
    const str = "do country:GB";
    const menu = buildSuggestions(str, 2, opts);
    expect(menu.frag).toBe("do");
    expect(menu.fragStart).toBe(0);
  });

  test("explicit domain: fragment yields a single domain entry", () => {
    const menu = buildSuggestions("domain:you", "domain:you".length, opts);
    expect(menu.groups.map((g) => g.name)).toEqual(["Domain"]);
    expect(menu.items[0].value).toBe("you");
    expect(menu.items[0].key).toBe("domain");
  });

  test("country is matched by name as well as code", () => {
    const menu = buildSuggestions("country:king", "country:king".length, opts);
    expect(menu.items.map((i) => i.value)).toContain("GB");
  });

  test("needsConnector is true after a completed term", () => {
    const str = "country:GB ";
    const menu = buildSuggestions(str, str.length, opts);
    expect(menu.needsConnector).toBe(true);
  });

  test("no suggestions when the caret is inside an existing term", () => {
    // Caret at the start of "label:nsfw" (to prepend - or NOT): the term is
    // already complete to the right of the caret, so suggesting a completion
    // would duplicate text. Menu must be empty.
    const str = "label:nsfw";
    expect(buildSuggestions(str, 0, opts).items).toEqual([]);
    // Caret between the key and value ("label:|nsfw") — same reasoning.
    expect(buildSuggestions(str, "label:".length, opts).items).toEqual([]);
    // Caret mid-word in the key ("lab|el:nsfw").
    expect(buildSuggestions(str, 3, opts).items).toEqual([]);
  });

  test("suggestions still appear at the end of a term being typed", () => {
    // Caret at the very end (nothing, or a space, to its right) is a real
    // completion point and must keep working.
    const menu = buildSuggestions("label:nsf", "label:nsf".length, opts);
    expect(menu.items.length).toBeGreaterThan(0);
  });
});

describe("acceptSuggestion", () => {
  test("inserts key:value and a trailing space", () => {
    const str = "you";
    const menu = buildSuggestions(str, str.length, {
      countries: [],
    });
    const sug = { key: "domain", value: "you", bare: true, idx: 0 };
    const r = acceptSuggestion(str, str.length, menu, sug);
    expect(r.queryStr).toBe("domain:you ");
  });
  test("prepends AND when a connector is needed", () => {
    const str = "domain:a coun";
    const caret = str.length;
    const menu = buildSuggestions(str, caret, {
      countries: [{ code: "GB", name: "United Kingdom" }],
    });
    const sug = { key: "country", value: "GB", bare: true, idx: 0 };
    const r = acceptSuggestion(str, caret, menu, sug);
    expect(r.queryStr).toBe("domain:a AND country:GB ");
  });
  test("typed fragment in an empty field gets no AND connector", () => {
    // Typing "g" to filter the country list must not be treated as a
    // preceding term — accepting GB yields just "country:GB ", no "AND".
    const str = "g";
    const menu = buildSuggestions(str, str.length, {
      countries: [{ code: "GB", name: "United Kingdom" }],
    });
    const sug = { key: "country", value: "GB", bare: true, idx: 0 };
    const r = acceptSuggestion(str, str.length, menu, sug);
    expect(r.queryStr).toBe("country:GB ");
  });
});

describe("buildQuery", () => {
  test("needs_triage, empty query", () => {
    const result = JSON.parse(
      buildQuery({
        activeState: "needs_triage",
        queryStr: "",
        triageStatus: null,
      }),
    );
    expect(result).toEqual({
      op: "AND",
      bug__isnull: true,
      triage_status__isnull: true,
    });
  });

  test("all, empty query", () => {
    const result = JSON.parse(
      buildQuery({ activeState: "all", queryStr: "", triageStatus: null }),
    );
    expect(result).toEqual({ op: "AND" });
  });

  test("triaged with specific status", () => {
    const result = JSON.parse(
      buildQuery({
        activeState: "triaged",
        queryStr: "",
        triageStatus: "worksforme",
      }),
    );
    expect(result).toEqual({ op: "AND", triage_status: "worksforme" });
  });

  test("whitespace-only query contributes nothing (no endswith '.')", () => {
    const result = JSON.parse(
      buildQuery({
        activeState: "needs_triage",
        queryStr: "   ",
        triageStatus: null,
      }),
    );
    expect(result).toEqual({
      op: "AND",
      bug__isnull: true,
      triage_status__isnull: true,
    });
  });

  test("domain query wraps state at 0 and typed query at 1", () => {
    const result = JSON.parse(
      buildQuery({
        activeState: "needs_triage",
        queryStr: "domain:example.com",
        triageStatus: null,
      }),
    );
    expect(result).toEqual({
      op: "AND",
      0: { op: "AND", bug__isnull: true, triage_status__isnull: true },
      1: { op: "OR", domain: "example.com", domain__endswith: ".example.com" },
    });
  });

  test("label query maps to reverse relation", () => {
    const result = JSON.parse(
      buildQuery({
        activeState: "all",
        queryStr: "label:nsfw",
        triageStatus: null,
      }),
    );
    expect(result).toEqual({
      op: "AND",
      0: { op: "AND" },
      1: { op: "AND", labels__label__name: "nsfw" },
    });
  });

  test("triaged + combined domain AND country", () => {
    const result = JSON.parse(
      buildQuery({
        activeState: "triaged",
        queryStr: "domain:youtube.com AND country:GB",
        triageStatus: "incomplete",
      }),
    );
    expect(result).toEqual({
      op: "AND",
      0: { op: "AND", triage_status: "incomplete" },
      1: {
        op: "AND",
        0: {
          op: "OR",
          domain: "youtube.com",
          domain__endswith: ".youtube.com",
        },
        1: { op: "AND", reportentry__country: "GB" },
      },
    });
  });
});

describe("buildBucketHash", () => {
  test("default needs_triage + empty query -> empty hash", () => {
    expect(
      buildBucketHash({
        activeState: "needs_triage",
        queryStr: "",
        currentPage: 1,
      }),
    ).toBe("");
  });

  test("non-default state is included", () => {
    expect(
      buildBucketHash({ activeState: "all", queryStr: "", currentPage: 1 }),
    ).toBe("#state=all");
  });

  test("page 1 is omitted, page 2+ is included", () => {
    expect(
      buildBucketHash({
        activeState: "needs_triage",
        queryStr: "",
        currentPage: 2,
      }),
    ).toBe("#page=2");
  });

  test("sort is included when present", () => {
    expect(
      buildBucketHash({
        activeState: "needs_triage",
        queryStr: "",
        currentPage: 1,
        sort: "-size,id",
      }),
    ).toBe("#sort=-size,id");
  });

  test("encodes the q field including spaces and parens", () => {
    const hash = buildBucketHash({
      activeState: "all",
      queryStr: "country:GB AND (domain:a OR domain:b)",
      currentPage: 1,
    });
    expect(hash).toContain("state=all");
    expect(hash).toContain(
      "q=country%3AGB%20AND%20(domain%3Aa%20OR%20domain%3Ab)",
    );
  });

  test("round-trips through parseHash", () => {
    const queryStr = "domain:youtube.com AND country:GB";
    const hash = buildBucketHash({
      activeState: "all",
      queryStr,
      currentPage: 3,
    });
    const parsed = parseHash(hash);
    expect(parsed.q).toBe(queryStr);
    expect(parsed.page).toBe("3");
  });

  test("triageStatus is persisted and round-trips through parseHash", () => {
    const hash = buildBucketHash({
      activeState: "triaged",
      queryStr: "",
      triageStatus: "worksforme",
      currentPage: 1,
    });
    expect(hash).toContain("triage_status=worksforme");
    expect(parseHash(hash).triage_status).toBe("worksforme");
  });

  test("triageStatus is omitted when falsy", () => {
    const hash = buildBucketHash({
      activeState: "all",
      queryStr: "",
      triageStatus: null,
      currentPage: 1,
    });
    expect(hash).not.toContain("triage_status");
  });
});
