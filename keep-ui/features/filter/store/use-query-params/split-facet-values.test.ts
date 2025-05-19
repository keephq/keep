import { splitFacetValues } from "./split-facet-values";

describe("splitFacetValues", () => {
  describe("splitFacetValues", () => {
    it("should split values by comma", () => {
      expect(splitFacetValues("null,1234,true")).toEqual([
        "null",
        "1234",
        "true",
      ]);
    });

    it("should handle values with spaces around commas with mixed string/boolean/number", () => {
      expect(splitFacetValues("'value1' , true , false , 12345")).toEqual([
        "'value1'",
        "true",
        "false",
        "12345",
      ]);
    });

    it("should handle single quoted values", () => {
      expect(splitFacetValues("'value1','value2','value3'")).toEqual([
        "'value1'",
        "'value2'",
        "'value3'",
      ]);
    });

    it("should handle escaped quotes inside quoted values", () => {
      expect(splitFacetValues("'value\\'1','value2'")).toEqual([
        "'value\\'1'",
        "'value2'",
      ]);
    });

    it("should handle escaped comma in quoted value", () => {
      expect(splitFacetValues("'first,second,third','value2',1234")).toEqual([
        "'first,second,third'",
        "'value2'",
        "1234",
      ]);
    });

    it("should handle escaped backslashes", () => {
      expect(splitFacetValues("value1\\,value2,value3")).toEqual([
        "value1\\,value2",
        "value3",
      ]);
    });

    it("should handle empty input", () => {
      expect(splitFacetValues("")).toEqual([]);
    });

    it("should handle input with leading commas", () => {
      expect(splitFacetValues(",value1,value2")).toEqual([
        "",
        "value1",
        "value2",
      ]);
    });

    it("should handle input with nested quotes", () => {
      expect(splitFacetValues("'value1,\\'nested\\',value2'")).toEqual([
        "'value1,\\'nested\\',value2'",
      ]);
    });
  });
});
