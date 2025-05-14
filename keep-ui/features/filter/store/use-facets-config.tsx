import { useEffect, useMemo } from "react";
import { FacetOptionDto, FacetsConfig } from "../models";
import { StoreApi, useStore } from "zustand";
import { FacetState } from "./create-facets-store";

export function useFacetsConfig(
  facetsConfig: FacetsConfig | undefined,
  store: StoreApi<FacetState>
) {
  const facets = useStore(store, (state) => state.facets);
  const setFacetsConfig = useStore(store, (state) => state.setFacetsConfig);

  useEffect(() => {
    if (!facets) {
      return;
    }

    const result: FacetsConfig = {};

    if (facets && Array.isArray(facets)) {
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
        const uncheckedByDefaultOptionValues =
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

    console.log(result);

    setFacetsConfig(result);
  }, [facetsConfig, facets, setFacetsConfig]);
}
