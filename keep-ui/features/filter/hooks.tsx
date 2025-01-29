import useSWR, { SWRConfiguration, useSWRConfig } from "swr";
import { CreateFacetDto, FacetDto, FacetOptionDto, FacetOptionsDict, FacetOptionsQueries, FacetOptionsQuery } from "./models";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { showErrorToast } from "@/shared/ui";
import { InitialFacetsData } from "./api";

export type UseFacetActionsValue = {
  addFacet: (incident: CreateFacetDto) => Promise<FacetDto>;
  deleteFacet: (id: string, skipConfirmation?: boolean) => Promise<boolean>;
};

export const useFacets = (
  entityName: string,
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();
  const requestUrl = `/${entityName}/facets`;

  const swrValue = useSWR<FacetDto[]>(
    () => (api.isReady() ? requestUrl : null),
    (url) => api.get(url),
    options
  );

  return {
    ...swrValue,
    isLoading: swrValue.isLoading || (!options.fallbackData && !api.isReady()),
  };
};

export const useFacetOptions = (
  entityName: string,
  initialFacetOptions: FacetOptionsDict | undefined,
  facetsQuery: FacetOptionsQuery | null
) => {
  const api = useApi();
  const [mergedFacetOptions, setMergedFacetOptions] = useState(
    initialFacetOptions
  );
  const [isLoading, setIsLoading] = useState(false);
  const requestUrl = `/${entityName}/facets/options`;

  useEffect(() => {
    if (!api.isReady() || !facetsQuery) {
      return;
    }

    async function fetch() {
      setIsLoading(true);
      const fetchedData: FacetOptionsDict = await api.post(
        requestUrl,
        facetsQuery
      );
      const newFacetOptions: FacetOptionsDict = JSON.parse(
        JSON.stringify(mergedFacetOptions || {})
      );
      Object.entries(fetchedData).forEach(([facetId, newOptions]) => {
        if (newFacetOptions[facetId]) {
          const currentFacetOptionsMap = newFacetOptions[facetId].reduce(
            (accumulator, oldOption) => {
              accumulator[oldOption.display_name] = oldOption;
              oldOption.matches_count = 0;
              return accumulator;
            },
            {} as Record<string, FacetOptionDto>
          );

          newOptions.forEach(
            (newOption) =>
              (currentFacetOptionsMap[newOption.display_name] = newOption)
          );
          newFacetOptions[facetId] = Object.values(currentFacetOptionsMap);
          return;
        }

        newFacetOptions[facetId] = newOptions;
      });

      setMergedFacetOptions(newFacetOptions);
      setIsLoading(false);
    }
    fetch();
  }, [api, api?.isReady(), JSON.stringify(facetsQuery), requestUrl]);

  return {
    facetOptions: mergedFacetOptions,
    isLoading
  };
};

export const useFacetActions = (
  entityName: string,
  initialFacetsData?: InitialFacetsData
): UseFacetActionsValue => {
  const requestUrl = `/${entityName}/facets`;

  const { mutate } = useSWRConfig();

  const mutateFacetsList = useCallback(
    () =>
      // Adding "?" to the key because the list always has a query param
      mutate((key) => typeof key === "string" && key == `/${entityName}/facets`),
    [mutate]
  );

  const api = useApi();

  const addFacet = useCallback(
    async (createFacet: CreateFacetDto) => {
      try {
        const result = await api.post(requestUrl, createFacet);
        mutateFacetsList();
        toast.success("Facet created successfully");
        return result as FacetDto;
      } catch (error) {
        showErrorToast(
          error,
          "Failed to create facet, please contact us if this issue persists."
        );
        throw error;
      }
    },
    [api, mutateFacetsList, requestUrl]
  );

  const deleteFacet = useCallback(
    async (facetId: string, skipConfirmation = false) => {
      if (
        !skipConfirmation &&
        !confirm("Are you sure you want to delete this facet?")
      ) {
        return false;
      }
      try {
        const result = await api.delete(`${requestUrl}/${facetId}`);
        mutateFacetsList();
        toast.success("Facet deleted successfully");
        return true;
      } catch (error) {
        showErrorToast(error, "Failed to delete facet");
        return false;
      }
    },
    [api, mutateFacetsList]
  );

  return {
    addFacet,
    deleteFacet,
  };
};
