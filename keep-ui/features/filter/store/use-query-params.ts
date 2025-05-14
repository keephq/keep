import { useEffect, useMemo, useRef, useState } from "react";
import { StoreApi, useStore } from "zustand";
import { FacetState } from "./create-facets-store";
import { FacetDto, FacetOptionDto, FacetOptionsQueries } from "../models";

export function useQueryParams(store: StoreApi<FacetState>) {
  const facets = useStore(store, (state) => state.facets);
  const allFacetOptions = useStore(store, (state) => state.facetOptions);
  const allFacetOptionsRef = useRef<Record<string, FacetOptionDto[]> | null>(
    null
  );
  allFacetOptionsRef.current = allFacetOptions;
  const facetsState = useStore(store, (state) => state.facetsState);
  const facetsStateRef = useRef(facetsState);
  facetsStateRef.current = facetsState;
  const facetsStateRefreshToken = useStore(
    store,
    (state) => state.facetsStateRefreshToken
  );

  const areQueryParamsSet = useStore(store, (state) => state.areQueryparamsSet);

  const patchFacetsState = useStore(store, (state) => state.patchFacetsState);
  const setAreQueryparamsSet = useStore(
    store,
    (state) => state.setAreQueryparamsSet
  );
  const isInitialStateHandled = useStore(
    store,
    (state) => state.isInitialStateHandled
  );

  const formattedFacets = useMemo(() => {
    if (!facets) {
      return null;
    }

    return facets
      .map((facet: FacetDto) => ({
        id: facet.id,
        queryParamName: "facet_" + facet.property_path.replace(/\./g, "_"),
      }))
      .sort((a, b) => a.queryParamName.localeCompare(b.queryParamName));
  }, [facets]);

  useEffect(() => {
    if (!isInitialStateHandled || areQueryParamsSet || !formattedFacets) {
      return;
    }

    const formattedFacetsDict: Record<string, string> = formattedFacets.reduce(
      (acc, curr) => ({ ...acc, [curr.queryParamName]: curr.id }),
      {}
    );
    const facetsStatePatch: Record<string, any> = {};
    const queryParams = new URLSearchParams(window.location.search);
    const facetEntries = Array.from(queryParams.entries()).filter(
      ([key, value]) => key.startsWith("facet_")
    );

    facetEntries.forEach(([key, value]) => {
      const facetId = formattedFacetsDict[key];

      if (!facetsStatePatch[facetId]) {
        facetsStatePatch[facetId] = {};
      }

      facetsStatePatch[facetId][value] = true;
    });

    patchFacetsState(facetsStatePatch);
    setAreQueryparamsSet(true);
  }, [
    formattedFacets,
    areQueryParamsSet,
    patchFacetsState,
    setAreQueryparamsSet,
    isInitialStateHandled,
  ]);

  useEffect(() => {
    if (!formattedFacets) {
      return;
    }

    const timeoutId = setTimeout(() => {
      const queryParams = new URLSearchParams(window.location.search);
      const currentQuery = window.location.search.replace(/^\?/, "");

      Array.from(queryParams.entries()).forEach(([key, value]) => {
        if (key.startsWith("facet_")) {
          queryParams.delete(key, value);
        }
      });

      formattedFacets.forEach((facet) => {
        const facetStateEntries = Object.entries(
          facetsStateRef.current[facet.id] || {}
        );
        const facetOptionsCount =
          allFacetOptionsRef.current?.[facet.id]?.length || 0;

        if (facetStateEntries.length === facetOptionsCount) {
          return;
        }

        facetStateEntries
          .filter(([key, value]) => value)
          .map(([key, value]) => key)
          .sort((a, b) => a.localeCompare(b))
          .forEach((key) => {
            queryParams.append(facet.queryParamName, key);
          });
      });

      const queryString = queryParams.toString();

      if (queryString !== currentQuery) {
        var newurl =
          window.location.origin + window.location.pathname + queryString
            ? `?${queryString}`
            : "";
        window.history.pushState({ path: newurl }, "", newurl);
      }
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [formattedFacets, facetsStateRefreshToken]);
}
