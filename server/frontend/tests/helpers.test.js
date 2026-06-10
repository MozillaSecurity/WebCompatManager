import { parseHash } from "../src/helpers.js";

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

  test("parses q=value pairs", () => {
    expect(parseHash("#status=all&q=domain%3Aa")).toEqual({
      status: "all",
      q: "domain:a",
    });
  });

  test("ignores a part without '='", () => {
    expect(parseHash("#status=all&garbage&page=2")).toEqual({
      status: "all",
      page: "2",
    });
  });
});
