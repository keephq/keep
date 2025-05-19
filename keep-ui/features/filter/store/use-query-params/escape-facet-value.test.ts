import { escapeFacetValue } from "./escape-facet-value";

describe("escapeFacetValue", () => {
  it("should escape backslashes, single quotes, and commas inside single-quoted strings", () => {
    const input = "'value\\with,special'characters'";
    const expected = "'value\\\\with\\,special\\'characters'";
    const actual = escapeFacetValue(input);
    expect(actual).toBe(expected);
  });

  it("should return the same string if it is not wrapped in single quotes", () => {
    const input = "valueWithoutQuotes";
    const expected = "valueWithoutQuotes";
    const actual = escapeFacetValue(input);
    expect(actual).toBe(expected);
  });

  it("should handle an empty single-quoted string", () => {
    const input = "''";
    const expected = "''";
    const actual = escapeFacetValue(input);
    expect(actual).toBe(expected);
  });

  it("should escape only the content inside single quotes", () => {
    const input = "'value,with'commas'";
    const expected = "'value\\,with\\'commas'";
    const actual = escapeFacetValue(input);
    expect(actual).toBe(expected);
  });

  it("should handle strings with only special characters", () => {
    const input = "'\\','";
    const expected = "'\\\\\\'\\,'";
    const actual = escapeFacetValue(input);
    expect(actual).toBe(expected);
  });

  it("should handle strings with no special characters", () => {
    const input = "'simpleValue'";
    const expected = "'simpleValue'";
    const actual = escapeFacetValue(input);
    expect(actual).toBe(expected);
  });
});
