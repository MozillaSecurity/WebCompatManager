import { buildHash, parseHash } from "../src/helpers.js";

describe("parseHash", () => {
  test("single value per key returns string", () => {
    expect(parseHash("#status=triaged&domain=example.com")).toEqual({
      status: "triaged",
      domain: "example.com",
    });
  });

  test("repeated keys return array", () => {
    expect(parseHash("#label=nsfw&label=worldcup2026")).toEqual({
      label: ["nsfw", "worldcup2026"],
    });
  });

  test("mixed single and repeated keys", () => {
    expect(parseHash("#status=triaged&label=nsfw&label=-worldcup2026")).toEqual(
      {
        status: "triaged",
        label: ["nsfw", "-worldcup2026"],
      },
    );
  });

  test("empty hash returns empty object", () => {
    expect(parseHash("#")).toEqual({});
  });

  test("decodes URI components", () => {
    expect(parseHash("#domain=example%2Ecom")).toEqual({
      domain: "example.com",
    });
  });
});

describe("buildHash", () => {
  test("needs_triage with no other filters returns empty hash", () => {
    expect(
      buildHash({
        activeState: "needs_triage",
        domainFilter: "",
        triageStatus: null,
        currentPage: 1,
        sort: null,
      }),
    ).toBe("");
  });

  test("non-default status is included", () => {
    expect(
      buildHash({
        activeState: "all",
        domainFilter: "",
        triageStatus: null,
        currentPage: 1,
        sort: null,
      }),
    ).toBe("#status=all");
  });

  test("domain filter is encoded and included", () => {
    expect(
      buildHash({
        activeState: "needs_triage",
        domainFilter: "example.com",
        triageStatus: null,
        currentPage: 1,
        sort: null,
      }),
    ).toBe("#domain=example.com");
  });

  test("triage status is encoded and included", () => {
    expect(
      buildHash({
        activeState: "triaged",
        domainFilter: "",
        triageStatus: "worksforme",
        currentPage: 1,
        sort: null,
      }),
    ).toBe("#status=triaged&triage_status=worksforme");
  });

  test("page 1 is omitted, page 2+ is included", () => {
    expect(
      buildHash({
        activeState: "needs_triage",
        domainFilter: "",
        triageStatus: null,
        currentPage: 2,
        sort: null,
      }),
    ).toBe("#page=2");
  });

  test("sort is included when present", () => {
    expect(
      buildHash({
        activeState: "needs_triage",
        domainFilter: "",
        triageStatus: null,
        currentPage: 1,
        sort: "-size,id",
      }),
    ).toBe("#sort=-size,id");
  });

  test("all params combined", () => {
    expect(
      buildHash({
        activeState: "triaged",
        domainFilter: "example.com",
        triageStatus: "worksforme",
        currentPage: 3,
        sort: "-size",
      }),
    ).toBe(
      "#status=triaged&domain=example.com&triage_status=worksforme&page=3&sort=-size",
    );
  });
});
