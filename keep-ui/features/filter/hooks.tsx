import useSWR, { SWRConfiguration, useSWRConfig } from "swr";
import useSWRInfinite from "swr/infinite";
import { CreateFacetDto, FacetDto, FacetOptionDto } from "./models";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { showErrorToast } from "@/shared/ui";

type UseFacetActionsValue = {
  addFacet: (incident: CreateFacetDto) => Promise<FacetDto>;
  deleteFacet: (id: string, skipConfirmation?: boolean) => Promise<boolean>;
};

export const useFacets = (
  facetsApiPath: string,
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();

  const swrValue = useSWR<FacetDto[]>(
    () => (api.isReady() ? facetsApiPath : null),
    (url) => api.get(url),
    options
  );

  return {
    ...swrValue,
    isLoading: swrValue.isLoading || (!options.fallbackData && !api.isReady()),
  };
};

export const useFacetOptions = (
  facetOptionsApiPath: string,
  facetOptionIdsToLoad: string[],
  cel: string = "",
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const [facetOptions, setFacetOptions] = useState<{ [facetId: string]: FacetOptionDto }>({});

  const api = useApi();

  const filtersParams = new URLSearchParams();

  if (cel) {
    filtersParams.set("cel", cel);
  }

  if (facetOptionIdsToLoad?.length) {
    filtersParams.set("facets_to_load", facetOptionIdsToLoad.join(","));
  }

  let queryString = "";

  if (filtersParams.toString()) {
    queryString = `?${filtersParams.toString()}`;
  }

  

  const swrValue = useSWR<{ [facetId: string]: FacetOptionDto }>(
    () => (api.isReady() ? facetOptionsApiPath + queryString : null),
    (url) => api.get(url),
    options
  );

  useEffect(() => {
    if (swrValue.data) {
        setFacetOptions({
            ...facetOptions,
            ...(swrValue.data as any)
        })
    }
  }, [swrValue.data]);

  return {
    ...swrValue,
    data: facetOptions,
    isLoading: swrValue.isLoading || (!options.fallbackData && !api.isReady()),
  };
};

export const useFacetActions = (facetsApiPath: string): UseFacetActionsValue => {
  const api = useApi();

  const { mutate } = useSWRConfig();

  const mutateFacetsList = useCallback(
    () =>
      // Adding "?" to the key because the list always has a query param
      mutate((key) => typeof key === "string" && key == "/incidents/facets"),
    [mutate]
  );

  const addFacet = useCallback(
    async (createFacet: CreateFacetDto) => {
      try {
        const result = await api.post(facetsApiPath, createFacet);
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
    [api, mutateFacetsList]
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
        const result = await api.delete(`${facetsApiPath}/${facetId}`);
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
