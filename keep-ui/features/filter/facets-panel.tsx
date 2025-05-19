import React, { useEffect, useMemo, useRef } from "react";
import { Facet } from "./facet";
import {
  FacetDto,
  FacetOptionDto,
  FacetOptionsQueries,
  FacetsConfig,
} from "./models";
import { PlusIcon, XMarkIcon } from "@heroicons/react/24/outline";
import "react-loading-skeleton/dist/skeleton.css";
import clsx from "clsx";
import { FacetStoreProvider, useFacetsConfig, useNewFacetStore } from "./store";
import { useStore } from "zustand";

export interface FacetsPanelProps {
  panelId: string;
  className: string;
  facets: FacetDto[];
  facetOptions: { [key: string]: FacetOptionDto[] };
  areFacetOptionsLoading?: boolean;
  /** Token to clear filters related to facets */
  clearFiltersToken?: string | null;
  /**
   * Object with facets that should be unchecked by default.
   * Key is the facet name, value is the list of option values to uncheck.
   **/
  facetsConfig?: FacetsConfig;
  renderFacetOptionLabel?: (
    facetName: string,
    optionDisplayName: string
  ) => JSX.Element | string | undefined;
  renderFacetOptionIcon?: (
    facetName: string,
    optionDisplayName: string
  ) => JSX.Element | undefined;
  onCelChange?: (cel: string) => void;
  onAddFacet: () => void;
  onDeleteFacet: (facetId: string) => void;
  onLoadFacetOptions: (facetId: string) => void;
  onReloadFacetOptions: (facetsQuery: FacetOptionsQueries) => void;
}

export const FacetsPanel: React.FC<FacetsPanelProps> = ({
  panelId,
  className,
  facets,
  facetOptions,
  areFacetOptionsLoading = false,
  clearFiltersToken,
  facetsConfig,
  onCelChange = undefined,
  onAddFacet = undefined,
  onDeleteFacet = undefined,
  onLoadFacetOptions = undefined,
  onReloadFacetOptions = undefined,
}) => {
  const facetOptionsRef = useRef<any>(facetOptions);
  facetOptionsRef.current = facetOptions;
  const onCelChangeRef = useRef(onCelChange);
  onCelChangeRef.current = onCelChange;
  const onReloadFacetOptionsRef = useRef(onReloadFacetOptions);
  onReloadFacetOptionsRef.current = onReloadFacetOptions;
  const store = useNewFacetStore(facetsConfig);
  const facetOptionQueries = useStore(
    store,
    (state) => state.queriesState.facetOptionQueries
  );
  const filterCel = useStore(store, (state) => state.queriesState.filterCel);

  const setAreOptionsReLoading = useStore(
    store,
    (state) => state.setAreOptionsReLoading
  );
  const setFacetOptions = useStore(store, (state) => state.setFacetOptions);
  const setFacets = useStore(store, (state) => state.setFacets);
  const clearFilters = useStore(store, (state) => state.clearFilters);

  useEffect(
    () => setAreOptionsReLoading(areFacetOptionsLoading),
    [areFacetOptionsLoading, setAreOptionsReLoading]
  );
  useEffect(
    () => setFacetOptions(facetOptions),
    [facetOptions, setFacetOptions]
  );
  useEffect(() => setFacets(facets), [facets, setFacets]);
  useEffect(() => {
    filterCel !== null && onCelChangeRef.current?.(filterCel);
  }, [filterCel]);
  useEffect(() => {
    facetOptionQueries && onReloadFacetOptionsRef.current?.(facetOptionQueries);
  }, [JSON.stringify(facetOptionQueries)]);

  useEffect(
    function clearFiltersWhenTokenChange(): void {
      if (clearFiltersToken) {
        clearFilters();
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    [clearFiltersToken, clearFilters]
  );

  return (
    <section
      id={`${panelId}-facets`}
      className={clsx("w-48 lg:w-56", className)}
      data-testid="facets-panel"
    >
      <div className="space-y-2">
        <div className="flex justify-between">
          {/* Facet button */}
          <button
            onClick={() => onAddFacet && onAddFacet()}
            className="p-1 pr-2 text-sm text-gray-600 hover:bg-gray-100 rounded flex items-center gap-1"
          >
            <PlusIcon className="h-4 w-4" />
            Add Facet
          </button>
          <button
            onClick={() => clearFilters()}
            className="p-1 pr-2 text-sm text-gray-600 hover:bg-gray-100 rounded flex items-center gap-1"
          >
            <XMarkIcon className="h-4 w-4" />
            Reset
          </button>
        </div>
        <FacetStoreProvider store={store}>
          {!facets &&
            [undefined, undefined, undefined].map((_, index) => (
              <Facet
                facet={
                  {
                    id: index.toString(),
                    name: "",
                    is_static: true,
                  } as FacetDto
                }
                key={index}
                isOpenByDefault={true}
              />
            ))}
          {facets &&
            facets.map((facet, index) => (
              <Facet
                key={facet.id}
                facet={facet}
                options={facetOptions?.[facet.id]}
                onLoadOptions={() =>
                  onLoadFacetOptions && onLoadFacetOptions(facet.id)
                }
                onDelete={() => onDeleteFacet && onDeleteFacet(facet.id)}
              />
            ))}
        </FacetStoreProvider>
      </div>
    </section>
  );
};
