import {
  validateQL,
  queryStrToJson,
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
