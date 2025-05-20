import { stringToValue, toFacetState, valueToString } from "../utils";

describe("utils", () => {
  describe("valueToString", () => {
    it("should return a string wrapped in single quotes", () => {
      expect(valueToString("test")).toBe("'test'");
    });

    it("should escape single quotes in the string", () => {
      expect(valueToString("it's a test")).toBe("'it\\'s a test'");
    });

    it("should return 'null' for null value", () => {
      expect(valueToString(null)).toBe("null");
    });

    it("should return 'null' for undefined value", () => {
      expect(valueToString(undefined)).toBe("null");
    });

    it("should return the string representation of a number", () => {
      expect(valueToString(123)).toBe("123");
    });

    it("should return the string representation of a boolean", () => {
      expect(valueToString(true)).toBe("true");
      expect(valueToString(false)).toBe("false");
    });

    it("should return the string representation of an object", () => {
      expect(valueToString({ key: "value" })).toBe("[object Object]");
    });

    it("should return the string representation of an array", () => {
      expect(valueToString([1, 2, 3])).toBe("1,2,3");
    });
  });

  describe("stringToValue", () => {
    it("should return null for the string 'null'", () => {
      expect(stringToValue("null")).toBeNull();
    });

    it("should return the original string if wrapped in single quotes", () => {
      expect(stringToValue("'test'")).toBe("test");
    });

    it("should unescape single quotes in the string", () => {
      expect(stringToValue("'it\\'s a test'")).toBe("it's a test");
    });

    it("should parse a valid JSON string", () => {
      expect(stringToValue('{"key":"value"}')).toEqual({ key: "value" });
    });

    it("should parse a valid JSON array string", () => {
      expect(stringToValue("[1,2,3]")).toEqual([1, 2, 3]);
    });

    it("should parse a number string", () => {
      expect(stringToValue("123")).toBe(123);
    });

    it("should parse a boolean string", () => {
      expect(stringToValue("true")).toBe(true);
      expect(stringToValue("false")).toBe(false);
    });
  });

  describe("toFacetState", () => {
    it("should return an empty object for an empty array", () => {
      expect(toFacetState([])).toEqual({});
    });

    it("should return an object with all values set to true", () => {
      expect(toFacetState(["value1", "value2"])).toEqual({
        value1: true,
        value2: true,
      });
    });

    it("should handle duplicate values in the array", () => {
      expect(toFacetState(["value1", "value1", "value2"])).toEqual({
        value1: true,
        value2: true,
      });
    });

    it("should handle special characters in the values", () => {
      expect(toFacetState(["value-1", "value_2"])).toEqual({
        "value-1": true,
        value_2: true,
      });
    });

    it("should handle numeric strings as keys", () => {
      expect(toFacetState(["123", "456"])).toEqual({
        "123": true,
        "456": true,
      });
    });
  });
});
