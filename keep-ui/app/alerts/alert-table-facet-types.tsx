import { AlertDto, Severity } from "./models";
import { Table } from "@tanstack/table-core";
import { DynamicFacet } from "./alert-table-facet-dynamic";

export interface FacetValue {
  label: string;
  count: number;
  isSelected: boolean;
}

export interface FacetFilters {
  [key: string]: string[];
}

export interface FacetValueProps {
  label: string;
  count: number;
  isSelected: boolean;
  onSelect: (value: string, exclusive: boolean, isAllOnly: boolean) => void;
  facetKey: string;
  showIcon?: boolean;
  facetFilters: FacetFilters;
}

export interface FacetProps {
  name: string;
  values: FacetValue[];
  onSelect: (value: string, exclusive: boolean, isAllOnly: boolean) => void;
  facetKey: string;
  facetFilters: FacetFilters;
  showIcon?: boolean;
  showSkeleton?: boolean;
}

export interface AlertFacetsProps {
  alerts: AlertDto[];
  facetFilters: FacetFilters;
  setFacetFilters: (
    filters: FacetFilters | ((filters: FacetFilters) => FacetFilters)
  ) => void;
  dynamicFacets: DynamicFacet[];
  setDynamicFacets: (
    facets: DynamicFacet[] | ((facets: DynamicFacet[]) => DynamicFacet[])
  ) => void;
  onDelete: (facetKey: string) => void;
  className?: string;
  table: Table<AlertDto>;
  showSkeleton?: boolean;
}
