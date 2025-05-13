import { useDebouncedValue } from "@/utils/hooks/useDebouncedValue";
import { useEffect } from "react";
import { StoreApi, useStore } from "zustand";
import { FacetState } from "./create-facets-store";
import { FacetOptionsQueries } from "../models";

export function useQueriesHandler(store: StoreApi<FacetState>) {
  const facetCelState = useStore(store, (state) => state.facetCelState);
  const facets = useStore(store, (state) => state.facets);
  const setQueriesState = useStore(store, (state) => state.setQueriesState);

  const [debouncedFacetCelState] = useDebouncedValue(facetCelState, 100);

  useEffect(() => {
    if (!debouncedFacetCelState) {
      return;
    }

    const facetOptionQueries: FacetOptionsQueries = {};

    if (!facets || !Array.isArray(facets)) {
      return;
    }

    facets.forEach((facet) => {
      const otherFacetCels = facets
        .filter((f) => f.id !== facet.id)
        .map((f) => debouncedFacetCelState?.[f.id])
        .filter(Boolean);

      facetOptionQueries[facet.id] = otherFacetCels
        .map((cel) => `(${cel})`)
        .join(" && ");
    });

    const filterCel = Object.values(debouncedFacetCelState || {})
      .filter(Boolean)
      .map((cel) => `(${cel})`)
      .join(" && ");
    setQueriesState(filterCel, facetOptionQueries);
  }, [debouncedFacetCelState, setQueriesState]);
}
