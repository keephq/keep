import useSWR, { SWRConfiguration, useSWRConfig } from "swr";
import {
  CreateFacetDto,
  FacetDto,
  FacetOptionDto,
  FacetOptionsDict,
  FacetOptionsQuery,
} from "./models";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useCallback, useEffect, useRef, useState } from "react";
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

export const useFacetPotentialFields = (
  entityName: string,
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();
  const requestUrl = `/${entityName}/facets/fields`;

  const swrValue = useSWR<string[]>(
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
  facetsQuery: FacetOptionsQuery | null,
  revalidationToken?: string | undefined,
  options: SWRConfiguration = {
    revalidateOnFocus: false,
    dedupingInterval: 3000,
  }
) => {
  const api = useApi();
  const isLoadingRef = useRef<boolean>(false);
  const [mergedFacetOptions, setMergedFacetOptions] =
    useState(initialFacetOptions);
  const requestUrl = `/${entityName}/facets/options`;

  const swrValue = useSWR<any>(
    () =>
      api.isReady() && facetsQuery
        ? requestUrl + "_" + JSON.stringify(facetsQuery)
        : null,
    async () => {
      isLoadingRef.current = true;
      const currentDate = new Date();
      const response = await api.post(requestUrl, facetsQuery);
      const responseTime = new Date().getTime() - currentDate.getTime();
      isLoadingRef.current = false;
      return {
        response,
        responseTime: responseTime,
      };
    },
    options
  );

  useEffect(() => {
    if (!swrValue.data?.response) {
      return;
    }

    const fetchedData: FacetOptionsDict = swrValue.data.response;
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
  }, [swrValue.data]);

  const [isSilentLoading, setIsSilentLoading] = useState<boolean>(false);
  const revalidationTokenRef = useRef<string | undefined>(revalidationToken);
  revalidationTokenRef.current = revalidationToken;
  const processedRevalidationTokenRef = useRef<string | undefined>(undefined);
  const refreshInterval = Math.ceil(
    Math.max((swrValue.data?.responseTime || 1) * 2, 5000)
  );

  useEffect(
    function watchRevalidationToken() {
      const intervalId = setInterval(() => {
        if (
          revalidationTokenRef.current !==
            processedRevalidationTokenRef.current &&
          !isLoadingRef.current
        ) {
          processedRevalidationTokenRef.current = revalidationTokenRef.current;
          setIsSilentLoading(true);
          swrValue.mutate();
        }
      }, refreshInterval);

      return () => clearInterval(intervalId);
    },
    // disabled as it should watch only responseTimeSeconds
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [refreshInterval, swrValue.mutate]
  );
  useEffect(() => setIsSilentLoading(false), [facetsQuery]);

  return {
    facetOptions: mergedFacetOptions,
    mutate: () => swrValue.mutate(),
    isLoading: !isSilentLoading && swrValue.isLoading,
    responseTime: swrValue.data?.responseTime,
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
      mutate(
        (key) => typeof key === "string" && key == `/${entityName}/facets`
      ),
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
