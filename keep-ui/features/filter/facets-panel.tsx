import React, { useEffect, useMemo, useState } from "react";
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

/**
 * It's facets state. Key is the facet id, and value is Set<string> of unselected options.
 * If facet option value is selected, the set will contain it's display value, otherwise it will not.
 */
type FacetState = {
  [facetId: string]: Set<string>;
};

function buildCel(
  facets: FacetDto[],
  facetOptions: { [key: string]: FacetOptionDto[] },
  facetsState: FacetState
): string {
  if (facetOptions == null) {
    return "";
  }

  const cel = Object.values(facets)
    .filter((facet) => facet.id in facetsState)
    .filter((facet) => facetOptions[facet.id])
    .map((facet) => {
      const notSelectedOptions = Object.values(facetOptions[facet.id])
        .filter((facetOption) =>
          facetsState[facet.id]?.has(facetOption.display_name)
        )
        .map((option) => {
          if (typeof option.value === "string") {
            /* Escape single-quote because single-quote is used for string literal mark*/
            const optionValue = option.value.replace(/'/g, "\\'");
            return `'${optionValue}'`;
          } else if (option.value == null) {
            return "null";
          }

          return option.value;
        });

      if (!notSelectedOptions.length) {
        return;
      }

      return `!(${facet.property_path} in [${notSelectedOptions.join(", ")}])`;
    })
    .filter((query) => query)
    .map((facetCel) => `${facetCel}`)
    .map((query) => query)
    .join(" && ");

  return cel;
}

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
  uncheckedByDefaultOptionValues?: { [key: string]: string[] };
  facetsConfig?: FacetsConfig;
  renderFacetOptionLabel?: (
    facetName: string,
    optionDisplayName: string
  ) => JSX.Element | string | undefined;
  renderFacetOptionIcon?: (
    facetName: string,
    optionDisplayName: string
  ) => JSX.Element | undefined;
  onCelChange: (cel: string) => void;
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
  const [clickedFacetId, setClickedFacetId] = useState<string | null>(null);
  const [celState, setCelState] = useState("");
  const [facetOptionQueries, setFacetOptionQueries] =
    useState<FacetOptionsQueries | null>(null);

  const facetsConfigIdBased = useMemo(() => {
    const result: FacetsConfig = {};

    if (facets) {
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
          facetConfig?.uncheckedByDefaultOptionValues;
        result[facet.id] = {
          sortCallback,
          renderOptionIcon,
          renderOptionLabel,
          uncheckedByDefaultOptionValues,
        };
      });
    }

    return result;
  }, [facetsConfig, facets]);

  function getFacetState(facetId: string): Set<string> {
    if (
      !defaultStateHandledForFacetIds.has(facetId) &&
      facetsConfigIdBased[facetId]?.uncheckedByDefaultOptionValues
    ) {
      const facetState = new Set<string>(...(facetsState[facetId] || []));
      const facet = facets.find((f) => f.id === facetId);

      if (facet) {
        facetsConfigIdBased[facetId]?.uncheckedByDefaultOptionValues.forEach(
          (optionValue) => facetState.add(optionValue)
        );
        defaultStateHandledForFacetIds.add(facetId);
      }

      facetsState[facetId] = facetState;
    }

    return facetsState[facetId] || new Set<string>();
  }

  useEffect(() => {
    const newFacetsState: FacetState = {};

    facets.forEach((facet) => {
      newFacetsState[facet.id] = getFacetState(facet.id);
    });

    setFacetsState(newFacetsState);
    // we need to run this effect only once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isOptionSelected = (facet_id: string, option_id: string) => {
    return !facetsState[facet_id] || !facetsState[facet_id].has(option_id);
  };

  useEffect(() => {
    var cel = buildCel(facets, facetOptions, facetsState);
    setCelState(cel);
  }, [facetsState, facetOptions, facets, celState, onCelChange]);

  useEffect(() => {
    if (facetOptionQueries) {
      onReloadFacetOptions && onReloadFacetOptions(facetOptionQueries);
    }
  }, [JSON.stringify(facetOptionQueries)]);

  useEffect(() => {
    const facetOptionQueries: FacetOptionsQueries = {};

    facets.forEach((facet) => {
      const otherFacets = facets.filter((f) => f.id !== facet.id);

      facetOptionQueries[facet.id] = buildCel(
        otherFacets,
        facetOptions,
        facetsState
      );
    });

    setFacetOptionQueries(facetOptionQueries);
    onCelChange && onCelChange(celState);
  }, [celState, onCelChange, setFacetOptionQueries]);

  function toggleFacetOption(facetId: string, value: string) {
    setClickedFacetId(facetId);
    const facetState = getFacetState(facetId);

    if (isOptionSelected(facetId, value)) {
      facetState.add(value);
    } else {
      facetState.delete(value);
    }

    setFacetsState({ ...facetsState, [facetId]: facetState });
  }

  function selectOneFacetOption(facetId: string, optionValue: string): void {
    setClickedFacetId(facetId);
    const facetState = getFacetState(facetId);

    facetOptions[facetId].forEach((facetOption) => {
      if (facetOption.display_name === optionValue) {
        facetState.delete(optionValue);
        return;
      }

      facetState.add(facetOption.display_name);
    });

    setFacetsState({
      ...facetsState,
      [facetId]: facetState,
    });
  }

  function selectAllFacetOptions(facetId: string) {
    setClickedFacetId(facetId);
    const facetState = getFacetState(facetId);

    Object.values(facetOptions[facetId]).forEach((option) =>
      facetState.delete(option.display_name)
    );

    setFacetsState({
      ...facetsState,
      [facetId]: facetState,
    });
  }

  function clearFilters(): void {
    setFacetsState({});
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
          [undefined, undefined, undefined].map((facet, index) => (
            <Facet
              key={index}
              name={""}
              isStatic={true}
              isOpenByDefault={true}
              optionsLoading={true}
              optionsReloading={false}
              facetState={new Set()}
              facetKey={`${index}`}
            />
          ))}

        {facets &&
          facets.map((facet, index) => (
            <Facet
              key={facet.id + index}
              name={facet.name}
              isStatic={facet.is_static}
              options={facetOptions?.[facet.id]}
              optionsLoading={!facetOptions?.[facet.id]}
              optionsReloading={
                areFacetOptionsLoading &&
                !!facet.id &&
                clickedFacetId !== facet.id
              }
              onSelect={(value) => toggleFacetOption(facet.id, value)}
              onSelectOneOption={(value) =>
                selectOneFacetOption(facet.id, value)
              }
              onSelectAllOptions={() => selectAllFacetOptions(facet.id)}
              facetState={getFacetState(facet.id)}
              facetKey={facet.id}
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
