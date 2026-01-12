import { MatchObjects } from "../src/helpers.js";

describe("MatchObjects", () => {
  let matcher;

  beforeEach(() => {
    matcher = new MatchObjects();
  });

  describe("ANY wildcard", () => {
    test("should match any string value", () => {
      const obj = { name: "test" };
      const signature = { name: MatchObjects.ANY };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should match any number value", () => {
      const obj = { count: 42 };
      const signature = { count: MatchObjects.ANY };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should match any boolean value", () => {
      const obj = { active: true };
      const signature = { active: MatchObjects.ANY };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should match any object value", () => {
      const obj = { data: { nested: "value" } };
      const signature = { data: MatchObjects.ANY };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should match null value", () => {
      const obj = { value: null };
      const signature = { value: MatchObjects.ANY };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should match undefined value", () => {
      const obj = { value: undefined };
      const signature = { value: MatchObjects.ANY };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should match multiple ANY wildcards", () => {
      const obj = { a: 1, b: "test", c: true };
      const signature = {
        a: MatchObjects.ANY,
        b: MatchObjects.ANY,
        c: MatchObjects.ANY,
      };
      expect(matcher.match(obj, signature)).toBe(true);
    });
  });

  describe("Type matching", () => {
    test("should reject when types do not match (string vs number)", () => {
      const obj = { value: "1" };
      const signature = { value: 1 };
      expect(matcher.match(obj, signature)).toBe(false);
    });

    test("should reject when types do not match (boolean vs number)", () => {
      const obj = { value: true };
      const signature = { value: 1 };
      expect(matcher.match(obj, signature)).toBe(false);
    });

    test("should reject when types do not match (string vs boolean)", () => {
      const obj = { value: "true" };
      const signature = { value: true };
      expect(matcher.match(obj, signature)).toBe(false);
    });

    test("should reject when types do not match (object vs string)", () => {
      const obj = { value: {} };
      const signature = { value: "object" };
      expect(matcher.match(obj, signature)).toBe(false);
    });
  });

  describe("Value matching", () => {
    test("should match exact string values", () => {
      const obj = { name: "test" };
      const signature = { name: "test" };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should reject non-matching string values", () => {
      const obj = { name: "test" };
      const signature = { name: "other" };
      expect(matcher.match(obj, signature)).toBe(false);
    });

    test("should match exact number values", () => {
      const obj = { count: 42 };
      const signature = { count: 42 };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should reject non-matching number values", () => {
      const obj = { count: 42 };
      const signature = { count: 43 };
      expect(matcher.match(obj, signature)).toBe(false);
    });

    test("should match exact boolean values", () => {
      const obj = { active: true };
      const signature = { active: true };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should reject non-matching boolean values", () => {
      const obj = { active: true };
      const signature = { active: false };
      expect(matcher.match(obj, signature)).toBe(false);
    });

    test("should match multiple key-value pairs", () => {
      const obj = { a: 1, b: "test", c: true };
      const signature = { a: 1, b: "test", c: true };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should reject if any value does not match", () => {
      const obj = { a: 1, b: "test", c: true };
      const signature = { a: 1, b: "test", c: false };
      expect(matcher.match(obj, signature)).toBe(false);
    });
  });

  describe("Key subset requirement", () => {
    test("should match when signature keys are subset of obj keys", () => {
      const obj = { a: 1, b: 2, c: 3 };
      const signature = { a: 1, b: 2 };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should match with empty signature", () => {
      const obj = { a: 1, b: 2 };
      const signature = {};
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should reject when signature has keys not in obj", () => {
      const obj = { a: 1, b: 2 };
      const signature = { a: 1, b: 2, c: 3 };
      expect(matcher.match(obj, signature)).toBe(false);
    });
  });

  describe("Nested objects", () => {
    test("should match simple nested objects", () => {
      const obj = { data: { name: "test", value: 42 } };
      const signature = { data: { name: "test", value: 42 } };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should reject non-matching nested objects", () => {
      const obj = { data: { name: "test", value: 42 } };
      const signature = { data: { name: "test", value: 43 } };
      expect(matcher.match(obj, signature)).toBe(false);
    });

    test("should match nested objects with subset of keys", () => {
      const obj = { data: { name: "test", value: 42, extra: "data" } };
      const signature = { data: { name: "test", value: 42 } };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should match deeply nested objects (3+ levels)", () => {
      const obj = {
        level1: {
          level2: {
            level3: {
              value: "deep",
            },
          },
        },
      };
      const signature = {
        level1: {
          level2: {
            level3: {
              value: "deep",
            },
          },
        },
      };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should reject deeply nested objects with non-matching values", () => {
      const obj = {
        level1: {
          level2: {
            level3: {
              value: "deep",
            },
          },
        },
      };
      const signature = {
        level1: {
          level2: {
            level3: {
              value: "shallow",
            },
          },
        },
      };
      expect(matcher.match(obj, signature)).toBe(false);
    });

    test("should match nested objects with ANY wildcard", () => {
      const obj = { data: { name: "test", value: 42 } };
      const signature = { data: { name: MatchObjects.ANY, value: 42 } };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should match nested object as ANY", () => {
      const obj = { data: { name: "test", value: 42 } };
      const signature = { data: MatchObjects.ANY };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should handle multiple keys with nested objects", () => {
      const obj = { a: { x: 1 }, b: 2 };
      const signature = { a: { x: 1 }, b: 2 };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should reject when non-nested key does not match", () => {
      const obj = { a: { x: 1 }, b: 2 };
      const signature = { a: { x: 1 }, b: 3 };
      expect(matcher.match(obj, signature)).toBe(false);
    });

    test("should reject when nested object does not match but other keys do", () => {
      const obj = { a: { x: 1 }, b: 2 };
      const signature = { a: { x: 2 }, b: 2 };
      expect(matcher.match(obj, signature)).toBe(false);
    });

    test("should handle multiple nested objects at same level", () => {
      const obj = {
        first: { a: 1, b: 2 },
        second: { x: "test", y: "value" },
        third: 42,
      };
      const signature = {
        first: { a: 1 },
        second: { x: "test" },
        third: 42,
      };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should reject if any nested object at same level does not match", () => {
      const obj = {
        first: { a: 1, b: 2 },
        second: { x: "test", y: "value" },
        third: 42,
      };
      const signature = {
        first: { a: 1 },
        second: { x: "wrong" },
        third: 42,
      };
      expect(matcher.match(obj, signature)).toBe(false);
    });
  });

  describe("Edge cases", () => {
    test("should match empty objects", () => {
      const obj = {};
      const signature = {};
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should match any object with empty signature", () => {
      const obj = { a: 1, b: 2, c: 3 };
      const signature = {};
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should reject empty object with non-empty signature", () => {
      const obj = {};
      const signature = { a: 1 };
      expect(matcher.match(obj, signature)).toBe(false);
    });

    test("should handle null values", () => {
      const obj = { value: null };
      const signature = { value: null };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should reject non-matching null values", () => {
      const obj = { value: null };
      const signature = { value: "not null" };
      expect(matcher.match(obj, signature)).toBe(false);
    });

    test("should handle undefined values", () => {
      const obj = { value: undefined };
      const signature = { value: undefined };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should reject null vs undefined mismatch", () => {
      const obj = { value: null };
      const signature = { value: undefined };
      expect(matcher.match(obj, signature)).toBe(false);
    });

    test("should handle arrays as objects", () => {
      const obj = { items: [1, 2, 3] };
      const signature = { items: [1, 2, 3] };
      expect(matcher.match(obj, signature)).toBe(true);
    });

    test("should reject non-matching arrays", () => {
      const obj = { items: [1, 2, 3] };
      const signature = { items: [1, 2, 4] };
      expect(matcher.match(obj, signature)).toBe(false);
    });
  });
});
