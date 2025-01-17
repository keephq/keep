import React, { useState } from "react";
import { Facet } from "./facet";
import { CreateFacetDto, FacetDto, FacetOptionDto, FacetOptionsQueries } from "./models";
import { PlusIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { AddFacetModal } from "./add-facet-modal";
import 'react-loading-skeleton/dist/skeleton.css';

type FacetState = {
  [facetId: string]: { [optionId: string]: boolean };
}

function buildCel(facets: FacetDto[], facetOptions: { [key: string]: FacetOptionDto[] }, facetsState: FacetState): string {
  const cel = Object.values(facets)
        .filter((facet) => facet.id in facetsState)
        .map((facet) => {
          const notSelectedOptions = Object.values(facetOptions[facet.id])
            .filter((facetOption) => facetsState[facet.id][facetOption.display_name] === false)
            .map((option) => {
              if (typeof option.value === 'string') {
                return `'${option.value}'`;
              } else if (option.value == null) {
                return 'null';
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
  onCelChange = undefined,
  onAddFacet = undefined,
  onDeleteFacet = undefined,
  onLoadFacetOptions = undefined,
  onReloadFacetOptions = undefined,
}) => {
  const [facetsState, setFacetsState] = useState<{
    [facetId: string]: { [optionId: string]: boolean };
  }>({});
  const [clickedFacetId, setClickedFacetId] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useLocalStorage<boolean>(
    `addFacetModalOpen-${panelId}`,
    false
  );
  const [celState, setCelState] = useState("");

  const isOptionSelected = (facet_id: string, option_id: string) => {
    return facetsState[facet_id]?.[option_id] !== false;
  }

  function calculateFacetsState(changedFacetId: string | null, newFacetsState: FacetState): void {
    setFacetsState(newFacetsState);
    var cel = buildCel(facets, facetOptions, newFacetsState);

    if (cel !== celState) {
      setCelState(cel);
      onCelChange && onCelChange(cel);
    }
    const facetOptionQueries: FacetOptionsQueries = {};

    facets.forEach((facet) => {
      const otherFacets = facets.filter((f) => f.id !== facet.id);

      facetOptionQueries[facet.id] = buildCel(otherFacets, facetOptions, newFacetsState);
    })

    onReloadFacetOptions && onReloadFacetOptions(facetOptionQueries)
  }

  function toggleFacetOption(facetId: string, value: string) {
    setClickedFacetId(facetId);
    const currentFacetState: any = facetsState[facetId] || {};
    currentFacetState[value] = !isOptionSelected(facetId, value);
    const newFacetsState = {
      ...facetsState,
      [facetId]: currentFacetState,
    };
    calculateFacetsState(facetId, newFacetsState);
  }

  function selectOneFacetOption(facetId: string, optionValue: string): void {
    setClickedFacetId(facetId);
    const newFacetState: any = {};

    facetOptions[facetId].forEach(facetOption => {
      if (facetOption.display_name === optionValue) {
        newFacetState[facetOption.display_name] = true;
        return;
      }

      newFacetState[facetOption.display_name] = false;
    })

    calculateFacetsState(facetId, {
      ...facetsState,
      [facetId]: newFacetState,
    });
  }

  function selectAllFacetOptions(facetId: string) {
    setClickedFacetId(facetId);
    const newFacetState: any = { ...facetsState[facetId] };
    Object.values(facetOptions[facetId]).forEach((option) => (newFacetState[option.display_name] = true));

    calculateFacetsState(null, {
      ...facetsState,
      [facetId]: newFacetState,
    });
  }

  return (
    <section id={`${panelId}-facets`} className={"min-w-56 max-w-56 " + className}>
      <div className="space-y-2">
        <div className="flex justify-between">
          {/* Facet button */}
          <button
            onClick={() => setIsModalOpen(true)}
            className="p-1 pr-2 text-sm text-gray-600 hover:bg-gray-100 rounded flex items-center gap-1"
          >
            <PlusIcon className="h-4 w-4" />
            Add Facet
          </button>
          <button
            onClick={() => calculateFacetsState(null, {})}
            className="p-1 pr-2 text-sm text-gray-600 hover:bg-gray-100 rounded flex items-center gap-1"
          >
            <XMarkIcon className="h-4 w-4" />
            Clear filters
          </button>
        </div>
        
        {facets?.map((facet, index) => (
          <Facet
            key={facet.id + index}
            name={facet.name}
            isStatic={facet.is_static}
            options={facetOptions?.[facet.id]}
            onSelect={(value) => toggleFacetOption(facet.id, value)}
            onSelectOneOption={(value) => selectOneFacetOption(facet.id, value)}
            onSelectAllOptions={() => selectAllFacetOptions(facet.id)}
            facetState={facetsState[facet.id]}
            facetKey={facet.id}
            showSkeleton={areFacetOptionsLoading && clickedFacetId !== facet.id}
            onLoadOptions={() => onLoadFacetOptions && onLoadFacetOptions(facet.id)}
            onDelete={() => onDeleteFacet && onDeleteFacet(facet.id)}
          />
        ))}

        {/* Facet Modal */}
        <AddFacetModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onAddFacet={(createFacet) => onAddFacet ? onAddFacet(createFacet) : null}
        />
      </div>
    </section>
  );
};
