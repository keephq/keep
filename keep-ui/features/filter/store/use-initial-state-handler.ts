import { StoreApi, useStore } from "zustand";
import { FacetsPanelState } from "./create-facets-store";
import { toFacetState, valueToString } from "./utils";
import { useEffect } from "react";

export function useInitialStateHandler(store: StoreApi<FacetsPanelState>) {
  const facetsConfig = useStore(store, (state) => state.facetsConfig);
  const facets = useStore(store, (state) => state.facets);
  const patchFacetsState = useStore(store, (state) => state.patchFacetsState);

  const isInitialStateHandled = useStore(
    store,
    (state) => state.isInitialStateHandled
  );
  const setIsInitialStateHandled = useStore(
    store,
    (state) => state.setIsInitialStateHandled
  );

  useEffect(() => {
    if (isInitialStateHandled || !facets || !facetsConfig) {
      return;
    }

    const facetsStatePatch: Record<string, any | null> = {};

    facets.forEach((facet) => {
      const facetConfig = facetsConfig?.[facet.id];

      if (facetConfig?.checkedByDefaultOptionValues) {
        facetsStatePatch[facet.id] = toFacetState(
          facetConfig.checkedByDefaultOptionValues.map((value) =>
            valueToString(value)
          )
        );
      }
    });

    setIsInitialStateHandled(true);

    if (Object.entries(facetsStatePatch).length) {
      patchFacetsState(facetsStatePatch);
    }
  }, [
    facetsConfig,
    facets,
    patchFacetsState,
    isInitialStateHandled,
    setIsInitialStateHandled,
  ]);
}
