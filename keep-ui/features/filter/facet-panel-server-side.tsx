import React, { useEffect, useState } from "react";
import { CreateFacetDto } from "./models";
import { useFacetActions, useFacetOptions, useFacets } from "./hooks";
import { InitialFacetsData } from "./api";
import { FacetsPanel } from "./facets-panel";

export interface FacetsPanelProps {
  panelId: string;
  className?: string;
  initialFacetsData?: InitialFacetsData;
  renderFacetOptionLabel?: (facetName: string, optionDisplayName: string) => JSX.Element | string | undefined;
  renderFacetOptionIcon?: (facetName: string, optionDisplayName: string) => JSX.Element | undefined;
  onCelChange?: (cel: string) => void;
  onAddFacet?: (createFacet: CreateFacetDto) => void;
  onDeleteFacet?: (facetId: string) => void;
}

export const FacetsPanelServerSide: React.FC<FacetsPanelProps> = ({
  panelId,
  className,
  initialFacetsData,
  onCelChange = undefined,
  onAddFacet = undefined,
  onDeleteFacet = undefined,
  renderFacetOptionIcon,
  renderFacetOptionLabel
}) => {
  const facetActions = useFacetActions("incidents", initialFacetsData);
  const [facetQueriesState, setFacetQueriesState] = useState<{ [key: string]: string } | null>(null);

  const { data: facetsData } = useFacets(
    "incidents",
    {
      revalidateOnFocus: false,
      revalidateOnMount: !initialFacetsData?.facets,
      fallbackData: initialFacetsData?.facets,
    }
  );

  const { facetOptions, isLoading } = useFacetOptions("incidents", initialFacetsData?.facetOptions, facetQueriesState);

  useEffect(() => {
    if (facetsData === initialFacetsData?.facets) {
        return;
    }

    const currentFacetQueriesState = facetQueriesState || {};
    const facetsNotInQuery = facetsData?.filter(facet => !(facet.id in currentFacetQueriesState));
    
    if (facetsNotInQuery?.length) {
        facetsNotInQuery.forEach((facet) => {
            currentFacetQueriesState[facet.id] = ""; // set empty CEL
        });
        
        setFacetQueriesState({ ...currentFacetQueriesState });
    }
  }, [facetsData, setFacetQueriesState]);

  return (
    <FacetsPanel
      panelId={panelId}
      className={className || ""}
      facets={(facetsData as any) || []}
      facetOptions={facetOptions as any || {}}
      areFacetOptionsLoading={isLoading}
      renderFacetOptionLabel={renderFacetOptionLabel}
      renderFacetOptionIcon={renderFacetOptionIcon}
      onCelChange={(cel: string) => {
        onCelChange && onCelChange(cel);
      }}
      onAddFacet={(createFacet) => {
        facetActions.addFacet(createFacet);
        onAddFacet && onAddFacet(createFacet);
      }}
      onLoadFacetOptions={(facetId) => {
        setFacetQueriesState({...facetQueriesState, [facetId]: ""});
      }}
      onDeleteFacet={(facetId) => {
        facetActions.deleteFacet(facetId);
        onDeleteFacet && onDeleteFacet(facetId);
      }}
      onReloadFacetOptions={(facetQueries) => setFacetQueriesState({...facetQueries})}
    ></FacetsPanel>
  );
};
