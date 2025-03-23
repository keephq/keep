export interface FacetConfig {
  uncheckedByDefaultOptionValues?: string[];
  renderOptionIcon?: (facetOption: FacetOptionDto) => JSX.Element | undefined;
  renderOptionLabel?: (
    facetOption: FacetOptionDto
  ) => JSX.Element | string | undefined;
  sortCallback?: (facetOption: FacetOptionDto) => number;
}

export interface FacetsConfig {
  [facetName: string]: FacetConfig;
}

export interface FacetOptionDto {
  display_name: string;
  value: any;
  matches_count: number;
}

export type FacetOptionsDict = { [facetId: string]: FacetOptionDto[] };
export type FacetOptionsQuery = {
  cel?: string | undefined;
  facet_queries?: FacetOptionsQueries;
};
export type FacetOptionsQueries = { [facet_id: string]: string };

export interface FacetDto {
  id: string;
  property_path: string;
  name: string;
  is_static: boolean;
  is_lazy: boolean;
}

export interface CreateFacetDto {
  property_path: string;
  name: string;
}
