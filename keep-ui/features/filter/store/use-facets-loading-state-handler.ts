import { useEffect } from "react";
import { FacetsPanelState } from "./create-facets-store";
import { StoreApi, useStore } from "zustand";

export function useFacetsLoadingStateHandler(
  store: StoreApi<FacetsPanelState>
) {
  const changedFacetId = useStore(store, (state) => state.changedFacetId);
  const allFacets = useStore(store, (state) => state.facets);
  const facetOptions = useStore(store, (state) => state.facetOptions);
  const areOptionsReLoading = useStore(
    store,
    (state) => state.areOptionsReLoading
  );
  const setChangedFacetId = useStore(store, (state) => state.setChangedFacetId);
  const setFacetOptionsLoadingState = useStore(
    store,
    (state) => state.setFacetOptionsLoadingState
  );

  useEffect(() => {
    const facetsLoadingState = Object.fromEntries(
      (allFacets?.map((facet) => {
        if (!facetOptions?.[facet.id]) {
          return [facet.id, "loading"];
        }

        if (facet.id !== changedFacetId && areOptionsReLoading) {
          return [facet.id, "reloading"];
        }

        return [facet.id, undefined];
      }) as [string, string][]) || []
    );

    setFacetOptionsLoadingState(facetsLoadingState);
  }, [
    facetOptions,
    changedFacetId,
    allFacets,
    areOptionsReLoading,
    setFacetOptionsLoadingState,
  ]);

  useEffect(() => {
    if (!areOptionsReLoading && !changedFacetId) {
      setChangedFacetId(null);
    }
  }, [areOptionsReLoading, changedFacetId, setChangedFacetId]);
}
