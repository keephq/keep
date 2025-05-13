import { useDebouncedValue } from "@/utils/hooks/useDebouncedValue";
import { useEffect, useMemo, useRef } from "react";
import { StoreApi, useStore } from "zustand";
import { FacetState } from "./create-facets-store";
import { FacetDto, FacetOptionDto, FacetOptionsQueries } from "../models";

function buildStringFacetCel(
  facet: FacetDto,
  facetOptions: FacetOptionDto[],
  facetState: Record<string, boolean>
): string {
  const values = Object.keys(facetState).filter((key) => facetState[key]);

  if (values.length === facetOptions?.length) {
    return "";
  }

  if (!values.length) {
    return "";
  }

  return `${facet.property_path} in [${values.join(", ")}]`;
}

function buildFacetsCelState(
  facets: FacetDto[],
  allFacetOptions: Record<string, FacetOptionDto[]>,
  facetsState: Record<string, any>
) {
  const facetCelState: Record<string, string> = {};

  facets.forEach((facet) => {
    facetCelState[facet.id] = buildStringFacetCel(
      facet,
      allFacetOptions[facet.id],
      facetsState[facet.id]
    );
  });

  return facetCelState;
}

export function useQueriesHandler(store: StoreApi<FacetState>) {
  const facetsState = useStore(store, (state) => state.facetsState);
  const facets = useStore(store, (state) => state.facets);
  const allFacetOptions = useStore(store, (state) => state.facetOptions);
  const allFacetOptionsRef = useRef(allFacetOptions);
  allFacetOptionsRef.current = allFacetOptions;
  const setQueriesState = useStore(store, (state) => state.setQueriesState);

  const [debouncedFacetsState] = useDebouncedValue(facetsState, 100);

  const facetsCelState = useMemo(() => {
    if (!debouncedFacetsState || !facets) {
      return null;
    }

    // console.log("ihor", debouncedFacetsState);

    return buildFacetsCelState(
      facets,
      allFacetOptionsRef.current || {},
      debouncedFacetsState
    );
  }, [debouncedFacetsState, setQueriesState]);

  useEffect(() => {
    if (!facetsCelState) {
      return;
    }

    const facetOptionQueries: FacetOptionsQueries = {};

    if (!facets || !Array.isArray(facets)) {
      return;
    }

    facets.forEach((facet) => {
      const otherFacetCels = facets
        .filter((f) => f.id !== facet.id)
        .map((f) => facetsCelState?.[f.id])
        .filter(Boolean);

      facetOptionQueries[facet.id] = otherFacetCels
        .map((cel) => `(${cel})`)
        .join(" && ");
    });

    const filterCel = Object.values(facetsCelState || {})
      .filter(Boolean)
      .map((cel) => `(${cel})`)
      .join(" && ");
    setQueriesState(filterCel, facetOptionQueries);
  }, [facetsCelState, facets]);
}
