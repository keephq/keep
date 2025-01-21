import React, { useEffect, useState } from "react";
import { CreateFacetDto } from "./models";
import { useFacetActions, useFacetOptions, useFacets } from "./hooks";
import { InitialFacetsData } from "./api";
import { FacetsPanel } from "./facets-panel";

export interface FacetsPanelProps {
  /** Entity name to fetch facets, e.g., "incidents" for /incidents/facets and /incidents/facets/options */
  entityName: string;
  className?: string;
  initialFacetsData?: InitialFacetsData;
  /** 
   * Revalidation token to force recalculation of the facets.
   * Will call API to recalculate facet options every revalidationToken value change
  */
  revalidationToken?: string | null;
  /** 
   * Token to clear filters related to facets.
   * Filters will be cleared every clearFiltersToken value change.
   **/
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
  /** Callback to handle the change of the CEL when options toggle */
  onCelChange?: (cel: string) => void;
}

export const FacetsPanelServerSide: React.FC<FacetsPanelProps> = ({
  entityName,
  className,
  initialFacetsData,
  revalidationToken,
  clearFiltersToken,
  onCelChange = undefined,
  uncheckedByDefaultOptionValues,
  renderFacetOptionIcon,
  renderFacetOptionLabel,
}) => {
  const facetActions = useFacetActions(entityName, initialFacetsData);
  const [facetQueriesState, setFacetQueriesState] = useState<{
    [key: string]: string;
  } | null>(null);

  const { data: facetsData } = useFacets(entityName, {
    revalidateOnFocus: false,
    revalidateOnMount: !initialFacetsData?.facets,
    fallbackData: initialFacetsData?.facets,
  });

  const { facetOptions, isLoading } = useFacetOptions(
    entityName,
    initialFacetsData?.facetOptions,
    facetQueriesState
  );

  useEffect(
    function reloadOptions() {
      if (facetsData === initialFacetsData?.facets) {
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

  useEffect(
    function watchRevalidationToken() {
      if (revalidationToken) {
        console.log({ revalidationToken, facetQueriesState });
        setFacetQueriesState(buildFacetsQueriesState());
      }
    },
    // disabled as it should watch only revalidationToken
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [revalidationToken]
  );

  return (
    <FacetsPanel
      panelId={entityName}
      className={className || ""}
      facets={(facetsData as any) || []}
      facetOptions={(facetOptions as any) || {}}
      areFacetOptionsLoading={isLoading}
      clearFiltersToken={clearFiltersToken}
      uncheckedByDefaultOptionValues={uncheckedByDefaultOptionValues}
      renderFacetOptionLabel={renderFacetOptionLabel}
      renderFacetOptionIcon={renderFacetOptionIcon}
      onCelChange={(cel: string) => {
        onCelChange && onCelChange(cel);
      }}
      onAddFacet={(createFacet) => facetActions.addFacet(createFacet)}
      onLoadFacetOptions={(facetId) => {
        setFacetQueriesState({ ...facetQueriesState, [facetId]: "" });
      }}
      onDeleteFacet={(facetId) => facetActions.deleteFacet(facetId)}
      onReloadFacetOptions={(facetQueries) =>
        setFacetQueriesState({ ...facetQueries })
      }
    ></FacetsPanel>
  );
};
