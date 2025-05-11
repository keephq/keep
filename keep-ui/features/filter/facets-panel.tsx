import React, { useEffect, useMemo, useRef, useState } from "react";
import { Facet } from "./facet";
import {
  FacetDto,
  FacetOptionDto,
  FacetOptionsQueries,
  FacetsConfig,
  FacetState,
} from "./models";
import { PlusIcon, XMarkIcon } from "@heroicons/react/24/outline";
import "react-loading-skeleton/dist/skeleton.css";
import clsx from "clsx";
import { useDebouncedValue } from "@/utils/hooks/useDebouncedValue";

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
  const defaultStateHandledForFacetIds = useMemo(() => new Set<string>(), []);
  const [facetsState, setFacetsState] = useState<FacetState>({});
  const [facetCelState, setFacetCelState] = useState<Record<
    string,
    string
  > | null>(null);
  const [debouncedFacetCelState] = useDebouncedValue(facetCelState, 100);

  const [facetOptionQueries, setFacetOptionQueries] =
    useState<FacetOptionsQueries | null>(null);
  const facetOptionsRef = useRef<any>(facetOptions);
  facetOptionsRef.current = facetOptions;
  const onCelChangeRef = useRef(onCelChange);
  onCelChangeRef.current = onCelChange;

  const facetsConfigIdBased = useMemo(() => {
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

    return result;
  }, [facetsConfig, facets]);
  const facetsConfigIdBasedRef = useRef(facetsConfigIdBased);
  facetsConfigIdBasedRef.current = facetsConfigIdBased;

  function getFacetState(facetId: string): Set<string> {
    if (
      !defaultStateHandledForFacetIds.has(facetId) &&
      facetsConfigIdBased[facetId]?.checkedByDefaultOptionValues
    ) {
      const facetState = new Set<string>(...(facetsState[facetId] || []));
      const facet = facets.find((f) => f.id === facetId);

      if (facet) {
        facetsConfigIdBased[facetId]?.checkedByDefaultOptionValues.forEach(
          (optionValue) => facetState.add(optionValue)
        );
        defaultStateHandledForFacetIds.add(facetId);
      }

      facetsState[facetId] = facetState;
    }

    return facetsState[facetId] || new Set<string>();
  }

  useEffect(() => {
    if (facetOptionQueries) {
      onReloadFacetOptions && onReloadFacetOptions(facetOptionQueries);
    }
  }, [JSON.stringify(facetOptionQueries)]);

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

    setFacetOptionQueries(facetOptionQueries);
    const filterCel = Object.values(debouncedFacetCelState || {})
      .filter(Boolean)
      .map((cel) => `(${cel})`)
      .join(" && ");
    onCelChangeRef.current && onCelChangeRef.current(filterCel);
  }, [debouncedFacetCelState, setFacetOptionQueries]);

  function clearFilters(): void {
    Object.keys(facetsState).forEach((facetId) => facetsState[facetId].clear());
    defaultStateHandledForFacetIds.clear();

    const newFacetsState: FacetState = {};

    facets.forEach((facet) => {
      newFacetsState[facet.id] = getFacetState(facet.id);
    });
    setFacetsState(newFacetsState);
  }

  useEffect(
    function clearFiltersWhenTokenChange(): void {
      if (clearFiltersToken) {
        clearFilters();
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    [clearFiltersToken]
  );

  const updateFacetsCelState = (facetId: string, facetCel: string) =>
    setFacetCelState({
      ...(facetCelState || {}),
      [facetId]: facetCel,
    });

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

        {!facets &&
          [undefined, undefined, undefined].map((_, index) => (
            <Facet
              facet={
                {
                  id: "",
                  name: "",
                  is_static: true,
                } as FacetDto
              }
              key={index}
              isOpenByDefault={true}
              optionsLoading={true}
              optionsReloading={false}
            />
          ))}

        {facets &&
          facets.map((facet, index) => (
            <Facet
              key={facet.id + index}
              facet={facet}
              onCelChange={(cel) => updateFacetsCelState(facet.id, cel)}
              options={facetOptions?.[facet.id]}
              optionsLoading={!facetOptions?.[facet.id]}
              optionsReloading={areFacetOptionsLoading && !!facet.id}
              facetConfig={facetsConfigIdBased[facet.id]}
              onLoadOptions={() =>
                onLoadFacetOptions && onLoadFacetOptions(facet.id)
              }
              onDelete={() => onDeleteFacet && onDeleteFacet(facet.id)}
            />
          ))}
      </div>
    </section>
  );
};
