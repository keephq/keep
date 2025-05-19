import { splitFacetValues } from "./split-facet-values";

describe("splitFacetValues", () => {
    describe("splitFacetValues", () => {
      it("should split values by comma", () => {
        const actual = splitFacetValues("null,1234,true");
        expect(actual).toEqual(["null", "1234", "true"]);
      });

      it("should handle values with spaces around commas with mixed string/boolean/number", () => {
        const actual = splitFacetValues("'value1' , true , false , 12345");
        expect(actual).toEqual(["'value1'", "true", "false", "12345"]);
      });

      it("should handle single quoted values", () => {
        const actual = splitFacetValues("'value1','value2','value3'");
        expect(actual).toEqual(["'value1'", "'value2'", "'value3'"]);
      });

      it("should handle escaped quotes inside quoted values", () => {
        const actual = splitFacetValues("'value\\'1','value2'");
        expect(actual).toEqual(["'value\\'1'", "'value2'"]);
      });

      it("should handle escaped comma in quoted value", () => {
        const actual = splitFacetValues("'first,second,third','value2',1234");
        expect(actual).toEqual(["'first,second,third'", "'value2'", "1234"]);
      });

      it("should handle escaped backslashes", () => {
        const actual = splitFacetValues("'value1\\\\',true,null");
        expect(actual).toEqual(["'value1\\\\'", "true", "null"]);
      });

      it("should handle empty input", () => {
        const actual = splitFacetValues("");
        expect(actual).toEqual([]);
      });

      it("should handle input with nested quotes", () => {
        const actual = splitFacetValues("'value1,\\'nested\\',value2'");
        expect(actual).toEqual(["'value1,\\'nested\\',value2'"]);
      });
    });
});
