import {
  BUCKET_FILTERS,
  registerCountryRankFilters,
} from "../src/bucket_filter_config.js";

describe("CountryRankBucketFilter", () => {
  beforeEach(() => {
    registerCountryRankFilters(["poland_rank"]);
  });

  afterEach(() => {
    delete BUCKET_FILTERS["poland_rank"];
  });

  test("toQuery with <= produces lte lookup", () => {
    const filter = BUCKET_FILTERS["poland_rank"];
    expect(filter.toQuery(1000, "<=")).toEqual({
      op: "AND",
      country_ranks__country: "poland_rank",
      country_ranks__rank__lte: 1000,
    });
  });

  test("toQuery with < produces lt lookup", () => {
    const filter = BUCKET_FILTERS["poland_rank"];
    expect(filter.toQuery(1000, "<")).toEqual({
      op: "AND",
      country_ranks__country: "poland_rank",
      country_ranks__rank__lt: 1000,
    });
  });

  test("toQuery with >= produces gte lookup", () => {
    const filter = BUCKET_FILTERS["poland_rank"];
    expect(filter.toQuery(500, ">=")).toEqual({
      op: "AND",
      country_ranks__country: "poland_rank",
      country_ranks__rank__gte: 500,
    });
  });

  test("toQuery with > produces gt lookup", () => {
    const filter = BUCKET_FILTERS["poland_rank"];
    expect(filter.toQuery(500, ">")).toEqual({
      op: "AND",
      country_ranks__country: "poland_rank",
      country_ranks__rank__gt: 500,
    });
  });

  test("toQuery with no op defaults to lte", () => {
    const filter = BUCKET_FILTERS["poland_rank"];
    expect(filter.toQuery(1000)).toEqual({
      op: "AND",
      country_ranks__country: "poland_rank",
      country_ranks__rank__lte: 1000,
    });
  });

  test("toQuery throws for a non-numeric value", () => {
    const filter = BUCKET_FILTERS["poland_rank"];
    expect(() => filter.toQuery("notanumber", "<=")).toThrow(
      /Invalid rank value: notanumber/,
    );
  });

  test("supportsComparison is true", () => {
    expect(BUCKET_FILTERS["poland_rank"].supportsComparison).toBe(true);
  });
});

describe("registerCountryRankFilters", () => {
  afterEach(() => {
    delete BUCKET_FILTERS["germany_rank"];
    delete BUCKET_FILTERS["global_rank"];
  });

  test("adds filter keys for each supplied column", () => {
    registerCountryRankFilters(["germany_rank", "global_rank"]);
    expect(BUCKET_FILTERS["germany_rank"]).toBeDefined();
    expect(BUCKET_FILTERS["global_rank"]).toBeDefined();
  });

  test("registered filter has the correct key and countryColumn", () => {
    registerCountryRankFilters(["germany_rank"]);
    const filter = BUCKET_FILTERS["germany_rank"];
    expect(filter.key).toBe("germany_rank");
    expect(filter.countryColumn).toBe("germany_rank");
  });

  test("calling with an empty array adds nothing", () => {
    const keysBefore = Object.keys(BUCKET_FILTERS).length;
    registerCountryRankFilters([]);
    expect(Object.keys(BUCKET_FILTERS).length).toBe(keysBefore);
  });
});
