import { StoreApi, useStore } from "zustand";
import { FacetState } from "./create-facets-store";
import { toFacetState, valueToString } from "./utils";
import { useEffect, useRef } from "react";

export function useInitialStateHandler(store: StoreApi<FacetState>) {
  const facetsConfig = useStore(store, (state) => state.facetsConfig);
  const facets = useStore(store, (state) => state.facets);
  const allFacetOptions = useStore(store, (state) => state.facetOptions);
  const patchFacetsState = useStore(store, (state) => state.patchFacetsState);
  const facetsState = useStore(store, (state) => state.facetsState);

  const facetsStateRef = useRef(facetsState);
  facetsStateRef.current = facetsState;

  const isInitialStateHandled = useStore(
    store,
    (state) => state.isInitialStateHandled
  );
  const setIsInitialStateHandled = useStore(
    store,
    (state) => state.setIsInitialStateHandled
  );

  const areFacetOptionsHandled = useStore(
    store,
    (state) => state.areFacetOptionsHandled
  );
  const setAreFacetOptionsHandled = useStore(
    store,
    (state) => state.setAreFacetOptionsHandled
  );

  useEffect(() => {
    if (isInitialStateHandled || !facets || !facetsConfig) {
      return;
    }

    const facetsStatePatch: Record<string, any> = {};

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
    patchFacetsState(facetsStatePatch);
  }, [
    facetsConfig,
    facets,
    patchFacetsState,
    isInitialStateHandled,
    setIsInitialStateHandled,
  ]);

  useEffect(() => {
    if (
      areFacetOptionsHandled ||
      !facets ||
      !allFacetOptions ||
      !facetsConfig
    ) {
      return;
    }

    const facetsStatePatch: Record<string, any> = {};

    facets.forEach((facet) => {
      if (facetsStateRef.current[facet.id]) {
        return;
      }

      const facetConfig = facetsConfig?.[facet.id];
      const facetOptions = allFacetOptions?.[facet.id];

      if (!facetConfig?.checkedByDefaultOptionValues) {
        facetsStatePatch[facet.id] = toFacetState(
          facetOptions.map((option) => valueToString(option.value))
        );
      }
    });

    setAreFacetOptionsHandled(true);
    patchFacetsState(facetsStatePatch);
  }, [
    facets,
    allFacetOptions,
    facetsConfig,
    areFacetOptionsHandled,
    setAreFacetOptionsHandled,
    patchFacetsState,
  ]);
}
