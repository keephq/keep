import { useMemo } from "react";
import { FacetDto, FacetOptionDto, FacetsConfig } from "../models";

export function useFacetsConfig(
  facets: FacetDto[],
  facetsConfig: FacetsConfig | undefined
) {
  const facetsConfigIdBased = useMemo(() => {
    const result: FacetsConfig = {};

    if (facets) {
      facets.forEach((facet) => {
        const facetConfig = facetsConfig?.[facet.name];
        const sortCallback =
          facetConfig?.sortCallback ||
          ((facetOption: FacetOptionDto) => facetOption.matches_count);
        const renderOptionIcon = facetConfig?.renderOptionIcon;
        const renderOptionLabel =
          facetConfig?.renderOptionLabel ||
          ((facetOption: FacetOptionDto) => (
            <span className="capitalize">{facetOption.display_name}</span>
          ));
        const checkedByDefaultOptionValues =
          facetConfig?.checkedByDefaultOptionValues;
        const canHitEmptyState = !!facetConfig?.canHitEmptyState;
        result[facet.id] = {
          sortCallback,
          renderOptionIcon,
          renderOptionLabel,
          checkedByDefaultOptionValues: uncheckedByDefaultOptionValues,
          canHitEmptyState,
        };
      });
    }

    return result;
  }, [facetsConfig, facets]);

  return facetsConfigIdBased;
}
