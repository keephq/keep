import React, { useEffect, useState } from "react";
import { FacetOptionsQueries, FacetOptionsQuery, FacetsConfig } from "./models";
import { useFacetActions, useFacetOptions, useFacets } from "./hooks";
import { InitialFacetsData } from "./api";
import { FacetsPanel } from "./facets-panel";
import { AddFacetModal } from "./add-facet-modal";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { AddFacetModalWithSuggestions } from "./add-facet-modal-with-suggestions";

export interface FacetsPanelProps {
  /** Entity name to fetch facets, e.g., "incidents" for /incidents/facets and /incidents/facets/options */
  entityName: string;
  className?: string;
  usePropertyPathsSuggestions?: boolean;
  initialFacetsData?: InitialFacetsData;
  /**
   * CEL to be used for fetching facet options.
   */
  facetOptionsCel?: string;
  /**
   * Revalidation token to force recalculation of the facets.
   * Will call API to recalculate facet options every revalidationToken value change
   */
  revalidationToken?: string;
  /**
   * Token to clear filters related to facets.
   * Filters will be cleared every clearFiltersToken value change.
   **/
  clearFiltersToken?: string | null;
  isSilentReloading?: boolean;
  facetsConfig?: FacetsConfig;
  /** Callback to handle the change of the CEL when options toggle */
  onCelChange?: (cel: string) => void;
}

export const FacetsPanelServerSide: React.FC<FacetsPanelProps> = ({
  entityName,
  usePropertyPathsSuggestions,
  facetOptionsCel,
  className,
  initialFacetsData,
  revalidationToken,
  clearFiltersToken,
  onCelChange = undefined,
  facetsConfig,
  isSilentReloading,
}) => {
  function buildFacetOptionsQuery() {
    if (!facetQueriesState) {
      return null;
    }

    let result: FacetOptionsQuery | null = null;

    if (facetOptionsCel) {
      result = {
        ...(result || {}),
        cel: facetOptionsCel,
      };
    }

    if (facetQueriesState) {
      result = {
        ...(result || {}),
        facet_queries: facetQueriesState,
      };
    }

    return result;
  }

  const [isModalOpen, setIsModalOpen] = useLocalStorage<boolean>(
    `addFacetModalOpen-${entityName}`,
    false
  );
  const facetActions = useFacetActions(entityName, initialFacetsData);
  const [facetQueriesState, setFacetQueriesState] =
    useState<FacetOptionsQueries | null>(null);

  const { data: facetsData } = useFacets(entityName, {
    revalidateOnFocus: false,
    revalidateOnMount: !initialFacetsData?.facets,
    fallbackData: initialFacetsData?.facets,
  });

  const {
    facetOptions,
    mutate: mutateFacetOptions,
    isLoading: facetOptionsLoading,
  } = useFacetOptions(
    entityName,
    initialFacetsData?.facetOptions as any,
    buildFacetOptionsQuery(),
    revalidationToken
  );

  useEffect(
    function reloadOptions() {
      if (
        facetsData === initialFacetsData?.facets &&
        initialFacetsData?.facetOptions
      ) {
        return;
      }

      const newFacetQueriesState = buildFacetsQueriesState();

      if (newFacetQueriesState) {
        setFacetQueriesState(newFacetQueriesState);
      }
    },
    // disabled because this effect uses currentFacetQueriesState that's also change in that effect
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [facetsData]
  );

  function buildFacetsQueriesState() {
    let newFacetQueriesState: { [key: string]: string } | undefined = undefined;

    facetsData?.forEach((facet) => {
      if (!newFacetQueriesState) {
        newFacetQueriesState = {};
      }
      if (facetQueriesState && facet.id in facetQueriesState) {
        newFacetQueriesState[facet.id] = facetQueriesState[facet.id];
      } else {
        newFacetQueriesState[facet.id] = "";
      }
    });

    if (newFacetQueriesState) {
      return newFacetQueriesState;
    }

    return null;
  }

  return (
    <>
      <FacetsPanel
        panelId={entityName}
        className={className || ""}
        facets={facetsData as any}
        facetOptions={facetOptions as any}
        areFacetOptionsLoading={!isSilentReloading && facetOptionsLoading}
        clearFiltersToken={clearFiltersToken}
        facetsConfig={facetsConfig}
        onCelChange={onCelChange}
        onAddFacet={() => setIsModalOpen(true)}
        onLoadFacetOptions={(facetId) => {
          setFacetQueriesState({ ...facetQueriesState, [facetId]: "" });
        }}
        onDeleteFacet={(facetId) => facetActions.deleteFacet(facetId)}
        onReloadFacetOptions={(facetQueries) =>
          setFacetQueriesState({ ...facetQueries })
        }
      ></FacetsPanel>
      {!usePropertyPathsSuggestions && (
        <AddFacetModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onAddFacet={(createFacet) => facetActions.addFacet(createFacet)}
        />
      )}
      {usePropertyPathsSuggestions && isModalOpen && (
        <AddFacetModalWithSuggestions
          entityName={entityName}
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onAddFacet={(createFacet) => facetActions.addFacet(createFacet)}
        />
      )}
    </>
  );
};
