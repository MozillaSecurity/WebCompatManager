import { buildQuery } from "../src/filter_helpers.js";

describe("buildQuery", () => {
  test("needs_triage: adds bug__isnull and triage_status__isnull", () => {
    const result = JSON.parse(
      buildQuery({
        activeState: "needs_triage",
        domainFilter: "",
        triageStatus: null,
      }),
    );
    expect(result).toEqual({
      op: "AND",
      bug__isnull: true,
      triage_status__isnull: true,
    });
  });

  test("all: no conditions", () => {
    const result = JSON.parse(
      buildQuery({ activeState: "all", domainFilter: "", triageStatus: null }),
    );
    expect(result).toEqual({ op: "AND" });
  });

  test("logged: bug__isnull false", () => {
    const result = JSON.parse(
      buildQuery({
        activeState: "logged",
        domainFilter: "",
        triageStatus: null,
      }),
    );
    expect(result).toEqual({ op: "AND", bug__isnull: false });
  });

  test("triaged without specific status: triage_status__isnull false", () => {
    const result = JSON.parse(
      buildQuery({
        activeState: "triaged",
        domainFilter: "",
        triageStatus: null,
      }),
    );
    expect(result).toEqual({ op: "AND", triage_status__isnull: false });
  });

  test("triaged with specific status: triage_status value, no __isnull", () => {
    const result = JSON.parse(
      buildQuery({
        activeState: "triaged",
        domainFilter: "",
        triageStatus: "worksforme",
      }),
    );
    expect(result).toEqual({ op: "AND", triage_status: "worksforme" });
    expect(result.triage_status__isnull).toBeUndefined();
  });

  test("domain filter wraps base query at 0 and domain sub-query at 1", () => {
    const result = JSON.parse(
      buildQuery({
        activeState: "needs_triage",
        domainFilter: "example.com",
        triageStatus: null,
      }),
    );
    expect(result).toEqual({
      op: "AND",
      0: { op: "AND", bug__isnull: true, triage_status__isnull: true },
      1: {
        op: "AND",
        domain__isnull: false,
        0: {
          op: "OR",
          domain: "example.com",
          domain__endswith: ".example.com",
        },
      },
    });
  });

  test("whitespace-only domain filter is ignored", () => {
    const result = JSON.parse(
      buildQuery({
        activeState: "needs_triage",
        domainFilter: "   ",
        triageStatus: null,
      }),
    );
    expect(result).toEqual({
      op: "AND",
      bug__isnull: true,
      triage_status__isnull: true,
    });
  });

  test("triaged + domain + triage status combined", () => {
    const result = JSON.parse(
      buildQuery({
        activeState: "triaged",
        domainFilter: "youtube.com",
        triageStatus: "incomplete",
      }),
    );
    expect(result).toEqual({
      op: "AND",
      0: { op: "AND", triage_status: "incomplete" },
      1: {
        op: "AND",
        domain__isnull: false,
        0: {
          op: "OR",
          domain: "youtube.com",
          domain__endswith: ".youtube.com",
        },
      },
    });
  });
});
