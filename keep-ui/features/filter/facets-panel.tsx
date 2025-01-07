import React, { useEffect, useState } from "react";
import { Facet } from "./facet";
import { FacetDto } from "./models";

export interface FacetsPanelProps {
  className: string;
  facets: FacetDto[];
  onCelChange: (cel: string) => void;
}

export const FacetsPanel: React.FC<FacetsPanelProps> = ({
  className,
  facets,
  onCelChange = undefined,
}) => {
  const facetsDict: { [key: string]: { [optionDisplayName: string]: any } } = facets.reduce(
    (result, facet) => {
      result[facet.id] = {};
      
      facet.options.forEach((option) => {
        result[facet.id][option.displayName] = option.value
      });

      return result;
    },
    {} as any
  );
  const initialFacetsState = facets.reduce((acc, facet) => {
    acc[facet.id] = facet.options.reduce((acc, option) => {
      acc[option.displayName] = true;
      return acc;
    }, {} as any);
    return acc;
  }, {} as any);

  const [fasetsState, setFacetsState] = useState<{
    [facetId: string]: { [optionId: string]: boolean };
  }>(initialFacetsState);

  function updateFacetsState(facetId: string, value: string) {
    const currentFacetState: any = fasetsState[facetId];
    currentFacetState[value] = !currentFacetState[value];

    setFacetsState({
      ...fasetsState,
      [facetId]: currentFacetState,
    });
  }

  function selectOneFacetOption(facetId: string, optionValue: string): void {
    const newFacetState = {
      [optionValue]: true,
    };

    Object.keys(fasetsState[facetId])
      .filter((key) => key !== optionValue)
      .forEach((key) => (newFacetState[key] = false));

    setFacetsState({
      ...fasetsState,
      [facetId]: newFacetState,
    });
  }

  function selectAllFacetOptions(facetId: string) {
    const facet = fasetsState[facetId];
    const newFacetState: any = { ...facet };
    Object.keys(facet).forEach(([key]) => newFacetState[key] = true);

    setFacetsState({
      ...fasetsState,
      [facetId]: newFacetState,
    });
  }

  useEffect(() => {
    if (onCelChange) {
      const cel = Object.entries(fasetsState)
        .map(([facetId, facetState]) => {
          return Object.entries(facetState)
            .filter(([, value]) => value)
            .map(([optionId]) => optionId)
            .map((optionDisplayName) => `${facetId} == '${facetsDict[facetId][optionDisplayName]}'`)
            .join(" || ");
        })
        .filter((query) => query)
        .map((facetCel) => `(${facetCel})`)
        .map(query => query)
        .join(" && ");
      onCelChange(cel);
    }
  }, [fasetsState, onCelChange, facetsDict]);

  return (
    <div className={"w-48 " + className}>
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
        {facets.map((facet) => (
          <Facet
            key={facet.id}
            name={facet.name}
            options={facet.options}
            onSelect={(value) => updateFacetsState(facet.id, value)}
            onSelectOneOption={(value) => selectOneFacetOption(facet.id, value)}
            onSelectAllOptions={() => selectAllFacetOptions(facet.id)}
            facetState={fasetsState[facet.id]}
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
