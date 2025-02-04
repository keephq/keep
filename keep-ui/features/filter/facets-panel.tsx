import React, { useEffect, useMemo, useState } from "react";
import { Facet } from "./facet";
import {
  CreateFacetDto,
  FacetDto,
  FacetOptionDto,
  FacetOptionsQueries,
} from "./models";
import { PlusIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { AddFacetModal } from "./add-facet-modal";
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
  const cel = Object.values(facets)
    .filter((facet) => facet.id in facetsState)
    .map((facet) => {
      const notSelectedOptions = Object.values(facetOptions[facet.id])
        .filter((facetOption) =>
          facetsState[facet.id]?.has(facetOption.display_name)
        )
        .map((option) => {
          if (typeof option.value === "string") {
            return `'${option.value}'`;
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
  renderFacetOptionLabel?: (
    facetName: string,
    optionDisplayName: string
  ) => JSX.Element | string | undefined;
  renderFacetOptionIcon?: (
    facetName: string,
    optionDisplayName: string
  ) => JSX.Element | undefined;
  onCelChange: (cel: string) => void;
  onAddFacet: (createFacet: CreateFacetDto) => void;
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
  uncheckedByDefaultOptionValues,
  renderFacetOptionIcon = undefined,
  renderFacetOptionLabel,
  onCelChange = undefined,
  onAddFacet = undefined,
  onDeleteFacet = undefined,
  onLoadFacetOptions = undefined,
  onReloadFacetOptions = undefined,
}) => {
  const defaultStateHandledForFacetIds = useMemo(() => new Set<string>(), []);
  const [facetsState, setFacetsState] = useState<FacetState>({});
  const [clickedFacetId, setClickedFacetId] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useLocalStorage<boolean>(
    `addFacetModalOpen-${panelId}`,
    false
  );
  const [celState, setCelState] = useState("");

  function getFacetState(facetId: string): Set<string> {
    if (
      !defaultStateHandledForFacetIds.has(facetId) &&
      uncheckedByDefaultOptionValues &&
      Object.keys(uncheckedByDefaultOptionValues).length
    ) {
      const facetState = new Set<string>(...(facetsState[facetId] || []));
      const facet = facets.find((f) => f.id === facetId);

      if (facet) {
        uncheckedByDefaultOptionValues[facet?.name]?.forEach((optionValue) =>
          facetState.add(optionValue)
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

    if (cel !== celState) {
      setCelState(cel);
      onCelChange && onCelChange(cel);
    }
    const facetOptionQueries: FacetOptionsQueries = {};

    facets.forEach((facet) => {
      const otherFacets = facets.filter((f) => f.id !== facet.id);

      facetOptionQueries[facet.id] = buildCel(
        otherFacets,
        facetOptions,
        facetsState
      );
    });

    onReloadFacetOptions && onReloadFacetOptions(facetOptionQueries);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facetsState]);

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
      className={clsx("min-w-48 max-w-48", className)}
    >
      <div className="space-y-2">
        <div className="flex justify-between">
          {/* Facet button */}
          <button
            onClick={() => setIsModalOpen(true)}
            className="p-1 pr-2 text-sm text-gray-600 hover:bg-gray-100 rounded flex items-center gap-1"
          >
            <PlusIcon className="h-4 w-4" />
            Add facet
          </button>
          <button
            onClick={() => clearFilters()}
            className="p-1 pr-2 text-sm text-gray-600 hover:bg-gray-100 rounded flex items-center gap-1"
          >
            <XMarkIcon className="h-4 w-4" />
            Reset
          </button>
        </div>

        {facets?.map((facet, index) => (
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
            onSelectOneOption={(value) => selectOneFacetOption(facet.id, value)}
            onSelectAllOptions={() => selectAllFacetOptions(facet.id)}
            facetState={getFacetState(facet.id)}
            facetKey={facet.id}
            renderOptionLabel={(optionDisplayName) =>
              renderFacetOptionLabel &&
              renderFacetOptionLabel(facet.name, optionDisplayName)
            }
            renderIcon={(optionDisplayName) =>
              renderFacetOptionIcon &&
              renderFacetOptionIcon(facet.name, optionDisplayName)
            }
            onLoadOptions={() =>
              onLoadFacetOptions && onLoadFacetOptions(facet.id)
            }
            onDelete={() => onDeleteFacet && onDeleteFacet(facet.id)}
          />
        ))}

        {/* Facet Modal */}
        <AddFacetModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onAddFacet={(createFacet) =>
            onAddFacet ? onAddFacet(createFacet) : null
          }
        />
      </div>
    </section>
  );
};
