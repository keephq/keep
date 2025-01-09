import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Facet } from "./facet";
import { FacetDto, FacetOptionDto } from "./models";

export interface FacetsPanelProps {
  className: string;
  facets: FacetDto[];
  facetOptions: { [key: string]: FacetOptionDto[] };
  onCelChange: (cel: string) => void;
}

export const FacetsPanel: React.FC<FacetsPanelProps> = ({
  className,
  facets,
  facetOptions,
  onCelChange = undefined,
}) => {
  const [celState, setCelState] = useState<string | undefined>(undefined);

  const [facetsState, setFacetsState] = useState<{
    [facetId: string]: { [optionId: string]: boolean };
  }>({});

  const isOptionSelected = (facet_id: string, option_id: string) => {
    return facetsState[facet_id]?.[option_id] !== false;
  }

  function toggleFacetOption(facetId: string, value: string) {
    const currentFacetState: any = facetsState[facetId] || {};
    currentFacetState[value] = !isOptionSelected(facetId, value);

    setFacetsState({
      ...facetsState,
      [facetId]: currentFacetState,
    });
  }

  function selectOneFacetOption(facetId: string, optionValue: string): void {
    const newFacetState: any = {};

    facetOptions[facetId].forEach(facetOption => {
      if (facetOption.display_name === optionValue) {
        newFacetState[facetOption.display_name] = true;
        return;
      }

      newFacetState[facetOption.display_name] = false;
    })

    setFacetsState({
      ...facetsState,
      [facetId]: newFacetState,
    });
  }

  function selectAllFacetOptions(facetId: string) {
    const newFacetState: any = { ...facetsState[facetId] };
    Object.values(facetOptions[facetId]).forEach((option) => (newFacetState[option.display_name] = true));

    setFacetsState({
      ...facetsState,
      [facetId]: newFacetState,
    });
  }

  useEffect(() => {
    if (onCelChange && facets && facetOptions && facetsState) {
      const cel = Object.values(facets)
        .filter((facet) => facet.id in facetsState)
        .map((facet) => {
          return Object.values(facetOptions[facet.id])
            .filter((facetOption) => facetsState[facet.id][facetOption.display_name] === false)
            .map(
              (option) =>
                `${facet.id} != ${ typeof option.value === "string" ? `"${option.value}"` : option.value}`
            )
            .join(" || ");
        })
        .filter((query) => query)
        .map((facetCel) => `(${facetCel})`)
        .map((query) => query)
        .join(" && ");


      console.log(cel);

      if (cel !== celState) {
        onCelChange(cel);
        setCelState(cel);
      }
    }
  }, [facetOptions, facets, facetsState, onCelChange]);

  return (
    <div className={"w-56 " + className}>
      <div className="space-y-2">
        {/* Facet button */}
        {/* <button
          onClick={() => setIsModalOpen(true)}
          className="w-full mt-2 px-2 py-1 text-sm text-gray-600 hover:bg-gray-100 rounded flex items-center gap-2"
        >
          <PlusIcon className="h-4 w-4" />
          Add Facet
        </button> */}

        {/* Dynamic facets */}
        {facets?.map((facet) => (
          <Facet
            key={facet.id}
            name={facet.name}
            options={facetOptions?.[facet.id] || []}
            onSelect={(value) => toggleFacetOption(facet.id, value)}
            onSelectOneOption={(value) => selectOneFacetOption(facet.id, value)}
            onSelectAllOptions={() => selectAllFacetOptions(facet.id)}
            facetState={facetsState[facet.id]}
            facetKey={facet.id}
            showSkeleton={false}
          />
        ))}

        {/* Facet Modal */}
        {/* <AddFacetModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          table={table}
          onAddFacet={handleAddFacet}
          existingFacets={[
            ...staticFacets,
            ...dynamicFacets.map((df) => df.key),
          ]}
        /> */}
      </div>
    </div>
  );
};
