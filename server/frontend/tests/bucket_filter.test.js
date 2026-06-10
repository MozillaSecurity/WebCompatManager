import {
  queryStrToServerQuery,
  buildQuery,
  buildBucketHash,
} from "../src/bucket_filter.js";
import { parseHash } from "../src/helpers.js";

describe("queryStrToServerQuery", () => {
  test("domain term -> OR endswith form", () => {
    expect(queryStrToServerQuery("domain:youtube.com").result).toEqual({
      op: "OR",
      domain: "youtube.com",
      domain__endswith: ".youtube.com",
    });
  });
  test("country term -> reverse-relation lookup", () => {
    expect(queryStrToServerQuery("country:GB").result).toEqual({
      op: "AND",
      reportentry__country: "GB",
    });
  });
  test("label term -> reverse-relation lookup", () => {
    expect(queryStrToServerQuery("label:nsfw").result).toEqual({
      op: "AND",
      labels__label__name: "nsfw",
    });
  });
  test("NOT wraps the inner term", () => {
    expect(queryStrToServerQuery("NOT country:GB").result).toEqual({
      op: "NOT",
      0: { op: "AND", reportentry__country: "GB" },
    });
  });
  test("AND of two terms indexes children", () => {
    expect(queryStrToServerQuery("country:GB AND domain:a").result).toEqual({
      op: "AND",
      0: { op: "AND", reportentry__country: "GB" },
      1: { op: "OR", domain: "a", domain__endswith: ".a" },
    });
  });
  test("implicit AND between adjacent terms", () => {
    expect(queryStrToServerQuery("domain:a country:GB").result).toEqual({
      op: "AND",
      0: { op: "OR", domain: "a", domain__endswith: ".a" },
      1: { op: "AND", reportentry__country: "GB" },
    });
  });
  test("a successful parse reports no error", () => {
    expect(queryStrToServerQuery("country:GB").error).toBeNull();
  });
  test("nested group -> nested JSON", () => {
    const { result } = queryStrToServerQuery(
      "domain:x AND (country:GB OR country:US)",
    );
    expect(result.op).toBe("AND");
    expect(result[1].op).toBe("OR");
    expect(result[1][0]).toEqual({ op: "AND", reportentry__country: "GB" });
  });
  test("empty parens contribute nothing and are not an error", () => {
    expect(queryStrToServerQuery("()")).toEqual({ result: null, error: null });
  });
  test("a term AND-ed with empty parens reduces to the term", () => {
    expect(queryStrToServerQuery("country:GB AND ()").result).toEqual({
      op: "AND",
      reportentry__country: "GB",
    });
  });
  test("unknown field is an error, not silently ignored", () => {
    const { result, error } = queryStrToServerQuery("bogus:x");
    expect(result).toBeNull();
    expect(error).toContain("bogus");
  });
  test("an unknown field anywhere in the query errors the whole query", () => {
    expect(
      queryStrToServerQuery("bogus:test AND label:valid").error,
    ).not.toBeNull();
  });
  test("comparison operator on a known field is an error", () => {
    expect(queryStrToServerQuery("label:>=10").error).not.toBeNull();
  });
  test("syntax error surfaces an error", () => {
    const { result, error } = queryStrToServerQuery("(domain:a");
    expect(result).toBeNull();
    expect(error).not.toBeNull();
  });
  // liqe binds AND/OR left-to-right at equal precedence (NOT conventional
  // OR-lowest). Documented so the behavior is intentional, not accidental.
  test("mixed AND/OR without parens binds left-to-right (liqe)", () => {
    const { result } = queryStrToServerQuery(
      "country:GB OR domain:a AND domain:b",
    );
    expect(result.op).toBe("AND");
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
