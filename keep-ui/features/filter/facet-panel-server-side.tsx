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
  const [loadedFacetIds, setLoadedFacetIds] = useState<Set<string> | undefined>(undefined);
//   const [facetsToLoadState, setFacetsToLoadState] = useState<string[]>([]);
  const facetActions = useFacetActions("incidents", initialFacetsData);

  const { data: facetsData, isLoading: facetsDataLoading } = useFacets(
    "incidents",
    {
      revalidateOnFocus: false,
      revalidateOnMount: !initialFacetsData?.facets,
      fallbackData: initialFacetsData?.facets,
    }
  );

  const { facetOptions, reloadFacetOptions } = useFacetOptions("incidents", initialFacetsData?.facetOptions);

  useEffect(() => {
    if (facetsData) {
        if (loadedFacetIds) {
            const diff = facetsData
                .filter(element => !loadedFacetIds.has(element.id));
            reloadFacetOptions(diff.map((f) => f.id));
        }

        setLoadedFacetIds(new Set(facetsData.map((f) => f.id)));
    }
  }, [facetsData, loadedFacetIds, setLoadedFacetIds]);

//   const { data: facetOptionsData, isLoading: facetsOptionsDataLoading } =
//     useFacetOptions("incidents", facetsToLoadState?.facetIds, facetsToLoadState?.cel, {
//       revalidateOnFocus: false,
//       revalidateOnMount: !initialFacetsData?.facetOptions,
//       fallbackData: initialFacetsData?.facetOptions,
//     });

  return (
    <FacetsPanel
      panelId={panelId}
      className={className || ""}
      facets={(facetsData as any) || []}
      facetOptions={facetOptions as any || {}}
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
      onReloadFacetOptions={(facetQueries) => reloadFacetOptions(facetQueries)}
    ></FacetsPanel>
  );
};
