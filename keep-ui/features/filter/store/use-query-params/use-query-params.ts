import { useEffect, useMemo, useRef } from "react";
import { StoreApi, useStore } from "zustand";
import { FacetsPanelState } from "../create-facets-store";
import { FacetDto, FacetOptionDto } from "../../models";
import { splitFacetValues } from "./split-facet-values";
import {
  ReadonlyURLSearchParams,
  useSearchParams,
  usePathname,
} from "next/navigation";

const facetQueryParamPrefix = "facet_";

function areFacetQueryParamsEqual(
  first: URLSearchParams,
  second: URLSearchParams
): boolean {
  const firstFacetValues = Array.from(first.entries()).filter(([key, value]) =>
    key.startsWith(facetQueryParamPrefix)
  );
  const secondFacetValues = Array.from(second.entries()).filter(
    ([key, value]) => key.startsWith(facetQueryParamPrefix)
  );

  if (firstFacetValues.length !== secondFacetValues.length) {
    return false;
  }
  const firstValuesMap = new Map(firstFacetValues);

  return !secondFacetValues.some(
    ([key, value]) => firstValuesMap.get(key) !== value
  );
}

function buildFacetQueryParams(
  formattedFacets: {
    id: string;
    queryParamName: string;
  }[],
  facetOptions: Record<string, FacetOptionDto[]>,
  facetsState: Record<string, any>
): URLSearchParams {
  const facetQueryParams = new URLSearchParams();

  formattedFacets.forEach((facet) => {
    if (!facetsState[facet.id]) {
      return;
    }

    const facetStateEntries = Object.entries(facetsState[facet.id] || {});
    const facetOptionsCount = facetOptions?.[facet.id]?.length || 0;

    if (facetStateEntries.length === facetOptionsCount) {
      return;
    }

    facetQueryParams.append(
      facet.queryParamName,
      facetStateEntries.map(([key, value]) => key).join(",")
    );
  });

  return facetQueryParams;
}

function replaceQueryParams(searchParams: URLSearchParams): void {
  window.history.replaceState(
    null,
    "",
    `${window.location.pathname}${searchParams.toString() ? "?" + searchParams.toString() : ""}`
  );
}

export function useQueryParams(store: StoreApi<FacetsPanelState>) {
  const searchParamsRef = useRef<ReadonlyURLSearchParams>();
  searchParamsRef.current = useSearchParams();
  const pathname = usePathname();
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

  const isFacetsStateInitializedFromQueryParams = useStore(
    store,
    (state) => state.isFacetsStateInitializedFromQueryParams
  );

  const patchFacetsState = useStore(store, (state) => state.patchFacetsState);
  const setIsFacetsStateInitializedFromQueryParams = useStore(
    store,
    (state) => state.setIsFacetsStateInitializedFromQueryParams
  );
  const isInitialStateHandled = useStore(
    store,
    (state) => state.isInitialStateHandled
  );

  useEffect(() => {
    return () => {
      const newParams = new URLSearchParams(searchParamsRef.current);
      const facetQueryParams = Array.from(newParams.entries()).filter(([key]) =>
        key.startsWith(facetQueryParamPrefix)
      );

      if (facetQueryParams.length) {
        facetQueryParams.forEach(([key, value]) =>
          newParams.delete(key, value)
        );
        replaceQueryParams(newParams);
      }
    };
  }, [pathname]);

  const formattedFacets = useMemo(() => {
    if (!facets) {
      return null;
    }

    return facets
      .map((facet: FacetDto) => ({
        id: facet.id,
        queryParamName:
          facetQueryParamPrefix + facet.property_path.replace(/\./g, "_"),
      }))
      .sort((a, b) => a.queryParamName.localeCompare(b.queryParamName));
  }, [facets]);

  useEffect(() => {
    if (
      !isInitialStateHandled ||
      isFacetsStateInitializedFromQueryParams ||
      !formattedFacets
    ) {
      return;
    }

    const formattedFacetsDict: Record<string, string> = formattedFacets.reduce(
      (acc, curr) => ({ ...acc, [curr.queryParamName]: curr.id }),
      {}
    );
    const facetsStatePatch: Record<string, any> = {};
    const queryParams = new URLSearchParams(searchParamsRef.current);
    const facetEntries = Array.from(queryParams.entries()).filter(([key]) =>
      key.startsWith(facetQueryParamPrefix)
    );

    facetEntries
      .map(([key, value]) => ({
        facetName: key,
        values: splitFacetValues(value),
      }))
      .forEach(({ facetName, values }) => {
        const facetId = formattedFacetsDict[facetName];

        if (!facetsStatePatch[facetId]) {
          facetsStatePatch[facetId] = {};
        }

        values?.forEach((value) => {
          if (!value) {
            return;
          }

          facetsStatePatch[facetId][value] = true;
        });
      });

    patchFacetsState(facetsStatePatch);
    setIsFacetsStateInitializedFromQueryParams(true);
  }, [
    formattedFacets,
    isFacetsStateInitializedFromQueryParams,
    patchFacetsState,
    setIsFacetsStateInitializedFromQueryParams,
    isInitialStateHandled,
  ]);

  useEffect(() => {
    if (!formattedFacets) {
      return;
    }

    const timeoutId = setTimeout(() => {
      const oldQueryParams = new URLSearchParams(searchParamsRef.current);

      const facetQueryParams = buildFacetQueryParams(
        formattedFacets,
        allFacetOptionsRef.current || {},
        facetsStateRef.current
      );

      if (areFacetQueryParamsEqual(facetQueryParams, oldQueryParams)) {
        return;
      }

      Array.from(oldQueryParams.entries())
        .filter(([key, value]) => key.startsWith(facetQueryParamPrefix))
        .forEach(([key, value]) => oldQueryParams.delete(key, value));

      Array.from(facetQueryParams.entries()).forEach(([key, value]) =>
        oldQueryParams.append(key, value)
      );

      replaceQueryParams(oldQueryParams);
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [formattedFacets, facetsStateRefreshToken]);
}
