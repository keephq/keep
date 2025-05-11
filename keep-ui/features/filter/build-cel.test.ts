import { buildCel } from "./build-cel";
import { FacetDto, FacetOptionDto, FacetsConfig, FacetState } from "./models";

describe("buildCel", () => {
  const facetsConfigIdBased: FacetsConfig = {
    facet3: {
      checkedByDefaultOptionValues: ["uncheckedOption5", "uncheckedOption6"],
    },
    facet4: {
      canHitEmptyState: true,
    },
  };

  it("should return an empty string if facetOptions is null", () => {
    const facets: FacetDto[] = [];
    const facetOptions = null;
    const facetsState: FacetState = {};

    const result = buildCel(
      facets,
      facetOptions,
      facetsState,
      facetsConfigIdBased
    );

    expect(result).toBe("");
  });

  it("should return an empty string if no facets match the state", () => {
    const facets: FacetDto[] = [
      { id: "facet1", property_path: "path1" } as FacetDto,
      { id: "facet2", property_path: "path2" } as FacetDto,
    ];
    const facetOptions: { [key: string]: FacetOptionDto[] } = {
      facet1: [{ display_name: "option1", value: "value1", matches_count: 1 }],
      facet2: [{ display_name: "option2", value: "value2", matches_count: 1 }],
    };
    const facetsState: FacetState = {};

    const result = buildCel(
      facets,
      facetOptions,
      facetsState,
      facetsConfigIdBased
    );

    expect(result).toBe("");
  });

  it("should build a CEL query for selected facets and options", () => {
    const facets: FacetDto[] = [
      { id: "facet1", property_path: "path1" } as FacetDto,
      { id: "facet2", property_path: "path2" } as FacetDto,
    ];
    const facetOptions: { [key: string]: FacetOptionDto[] } = {
      facet1: [
        { display_name: "option1", value: "value1", matches_count: 1 },
        { display_name: "option2", value: "value2", matches_count: 0 },
      ],
      facet2: [
        { display_name: "option3", value: "value3", matches_count: 1 },
        { display_name: "option4", value: "value4", matches_count: 1 },
      ],
    };
    const facetsState: FacetState = {
      facet1: new Set(["option2"]),
      facet2: new Set(["option3"]),
    };

    const result = buildCel(
      facets,
      facetOptions,
      facetsState,
      facetsConfigIdBased
    );

    expect(result).toBe("(path1 in ['value1']) && (path2 in ['value4'])");
  });

  it("should include facet option with 0 matches count if the facet can hit empty state", () => {
    const facets: FacetDto[] = [
      { id: "facet1", property_path: "path1" } as FacetDto,
      { id: "facet4", property_path: "path4" } as FacetDto,
    ];
    const facetOptions: { [key: string]: FacetOptionDto[] } = {
      facet1: [
        { display_name: "option1", value: "value1", matches_count: 1 },
        { display_name: "option2", value: "value2", matches_count: 0 },
      ],
      facet4: [
        { display_name: "option3", value: "value3", matches_count: 1 },
        { display_name: "option4", value: "value4", matches_count: 1 },
        { display_name: "option5", value: "value5", matches_count: 0 },
      ],
    };
    const facetsState: FacetState = {
      facet1: new Set(["option2"]),
      facet4: new Set(["option3"]),
    };

    const result = buildCel(
      facets,
      facetOptions,
      facetsState,
      facetsConfigIdBased
    );

    expect(result).toBe(
      "(path1 in ['value1']) && (path4 in ['value4', 'value5'])"
    );
  });

  it("should not include options with 0 matches count to filter", () => {
    ////////
    const facets: FacetDto[] = [
      { id: "facet1", property_path: "path1" } as FacetDto,
      { id: "facet2", property_path: "path2" } as FacetDto,
    ];
    const facetOptions: { [key: string]: FacetOptionDto[] } = {
      facet1: [
        { display_name: "option1", value: "value1", matches_count: 1 },
        { display_name: "option2", value: "value2", matches_count: 0 },
      ],
      facet2: [
        { display_name: "option3", value: "value3", matches_count: 1 },
        { display_name: "option4", value: "value4", matches_count: 1 },
      ],
    };
    const facetsState: FacetState = {
      facet1: new Set(["option1"]),
      facet2: new Set(["option3"]),
    };

    const result = buildCel(
      facets,
      facetOptions,
      facetsState,
      facetsConfigIdBased
    );

    expect(result).toBe("(path2 in ['value4'])");
  });

  it("should escape single quotes in string values", () => {
    const facets: FacetDto[] = [
      { id: "facet1", property_path: "path1" } as FacetDto,
    ];
    const facetOptions: { [key: string]: FacetOptionDto[] } = {
      facet1: [
        {
          display_name: "option1",
          value: "value'with'quotes",
          matches_count: 1,
        },
        {
          display_name: "option2",
          value: "some value",
          matches_count: 2,
        },
      ],
    };
    const facetsState: FacetState = {
      facet1: new Set(["option2"]),
    };

    const result = buildCel(
      facets,
      facetOptions,
      facetsState,
      facetsConfigIdBased
    );

    expect(result).toBe("(path1 in ['value\\'with\\'quotes'])");
  });

  it("should handle null values in facet options", () => {
    const facets: FacetDto[] = [
      { id: "facet1", property_path: "path1" } as FacetDto,
    ];
    const facetOptions: { [key: string]: FacetOptionDto[] } = {
      facet1: [
        { display_name: "None", value: null, matches_count: 1 },
        { display_name: "some option", value: "something", matches_count: 2 },
      ],
    };
    const facetsState: FacetState = {
      facet1: new Set(["some option"]),
    };

    const result = buildCel(
      facets,
      facetOptions,
      facetsState,
      facetsConfigIdBased
    );

    expect(result).toBe("(path1 in [null])");
  });

  it("should return an empty string if no options are selected", () => {
    const facets: FacetDto[] = [
      { id: "facet1", property_path: "path1" } as FacetDto,
    ];
    const facetOptions: { [key: string]: FacetOptionDto[] } = {
      facet1: [{ display_name: "option1", value: "value1", matches_count: 0 }],
    };
    const facetsState: FacetState = {
      facet1: new Set(),
    };

    const result = buildCel(
      facets,
      facetOptions,
      facetsState,
      facetsConfigIdBased
    );

    expect(result).toBe("");
  });
});
