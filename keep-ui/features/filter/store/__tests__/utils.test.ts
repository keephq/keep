import { stringToValue, toFacetState, valueToString } from "../utils";

describe("utils", () => {
  describe("valueToString", () => {
    describe("for strings", () => {
      it("should return a string wrapped in single quotes", () => {
        expect(valueToString("test")).toBe("'test'");
      });

      it("should escape single quotes in the string", () => {
        expect(valueToString("it's a test and it's a test")).toBe(
          "'it\\'s a test and it\\'s a test'"
        );
      });

      it("should escape comma in the string", () => {
        expect(valueToString("first, second, third")).toBe(
          "'first\\, second\\, third'"
        );
      });

      it("should escape back slash in the string", () => {
        expect(valueToString("first\\second\\third")).toBe(
          "'first\\\\second\\\\third'"
        );
      });
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
  });

  describe("stringToValue", () => {
    describe("for strings", () => {
      it("should return the original string if wrapped in single quotes", () => {
        expect(stringToValue("'test'")).toBe("test");
      });

      it("should unescape single quotes in the string", () => {
        expect(stringToValue("'it\\'s a test and it\\'s a test'")).toBe(
          "it's a test and it's a test"
        );
      });

      it("should unescape comma in the string", () => {
        expect(stringToValue("'first\\,second\\,third'")).toBe(
          "first,second,third"
        );
      });

      it("should unescape back slash in the string", () => {
        expect(stringToValue("'first\\\\second\\\\third'")).toBe(
          "first\\second\\third"
        );
      });
    });

    it("should return null for the string 'null'", () => {
      expect(stringToValue("null")).toBeNull();
    });

    it("should parse a number string", () => {
      expect(stringToValue("123.34")).toBe(123.34);
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
