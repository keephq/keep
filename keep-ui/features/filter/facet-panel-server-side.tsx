import React, { useEffect, useState } from "react";
import { CreateFacetDto, FacetDto } from "./models";
import { useFacetActions, useFacetOptions, useFacets } from "./hooks";
import { InitialFacetsData } from "./api";
import { FacetsPanel } from "./facets-panel";

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
  const [celForFacetsState, setCelForFacetsState] = useState("");
  const [facetIdsLoaded, setFacetIdsLoaded] = useState<string[]>([]);
  const [facetsToLoadState, setFacetsToLoadState] = useState<{ cel: string, facetIds: string[]} | undefined>(undefined);

  const facetActions = useFacetActions("incidents");

  const { data: facetsData, isLoading: facetsDataLoading } = useFacets(
    "incidents",
    {
      revalidateOnFocus: false,
      revalidateOnMount: !initialFacetsData?.facets,
      fallbackData: initialFacetsData?.facets,
    }
  );

  const { data: facetOptionsData, isLoading: facetsOptionsDataLoading } =
    useFacetOptions("incidents", facetsToLoadState?.facetIds || initialFacetsData?.facets?.map((facet) => facet.id), facetsToLoadState?.cel, {
      revalidateOnFocus: false,
      revalidateOnMount: !initialFacetsData?.facetOptions,
      fallbackData: initialFacetsData?.facetOptions,
    });

  return (
    <FacetsPanel
      panelId={panelId}
      className={className || ""}
      facets={(facetsData as any) || []}
      facetOptions={facetOptionsData as any}
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
      onReloadFacetOptions={(facetsToReload, cel) => setFacetsToLoadState({ cel, facetIds: facetsToReload.map(f => f.id) })}
    ></FacetsPanel>
  );
};
