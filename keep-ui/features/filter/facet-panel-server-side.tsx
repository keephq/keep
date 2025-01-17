import React, { useEffect, useState } from "react";
import { CreateFacetDto, FacetDto } from "./models";
import { useFacetActions, useFacetOptions, useFacets } from "./hooks";
import { InitialFacetsData } from "./api";
import { FacetsPanel } from "./facets-panel";
import { init } from "@sentry/nextjs";

export interface FacetsPanelProps {
  panelId: string;
  className?: string;
  initialFacetsData?: InitialFacetsData;
  onCelChange?: (cel: string) => void;
  onAddFacet?: (createFacet: CreateFacetDto) => void;
  onDeleteFacet?: (facetId: string) => void;
  onLoadFacetOptions?: (facetId: string) => void;
  onIsLoading?: (isLoading: boolean) => void;
}

export const FacetsPanelServerSide: React.FC<FacetsPanelProps> = ({
  panelId,
  className,
  initialFacetsData,
  onCelChange = undefined,
  onAddFacet = undefined,
  onDeleteFacet = undefined,
  onLoadFacetOptions = undefined,
  onIsLoading,
}) => {
  const [celState, setCelState] = useState("");
//   const [celForFacetsState, setCelForFacetsState] = useState("");
  const [facetIdsLoaded, setFacetIdsLoaded] = useState<string[]>([]);
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
      onCelChange={(cel: string) => {
        setCelState(cel);
        onCelChange && onCelChange(cel);
      }}
      onAddFacet={(createFacet) => {
        facetActions.addFacet(createFacet);
        onAddFacet && onAddFacet(createFacet);
      }}
      onLoadFacetOptions={(facetId) => {
        setFacetIdsLoaded([facetId]);
        onLoadFacetOptions && onLoadFacetOptions(facetId);
      }}
      onDeleteFacet={(facetId) => {
        facetActions.deleteFacet(facetId);
        onDeleteFacet && onDeleteFacet(facetId);
      }}
      onReloadFacetOptions={(facetQueries) => setFacetQueriesState({...facetQueries})}
    ></FacetsPanel>
  );
};
