import useSWR, { SWRConfiguration } from "swr";
import { FacetDto, FacetOptionDto } from "./models";
import { useApi } from "@/shared/lib/hooks/useApi";

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
  const api = useApi();

  const filtersParams = new URLSearchParams();

  if (cel) {
    filtersParams.set("cel", cel);
  }

  if (facetOptionIdsToLoad?.length) {
    filtersParams.set("facet_option_ids", facetOptionIdsToLoad.join(","));
  }

  let queryString = ''

  if (filtersParams.toString()) {
    queryString = `?${filtersParams.toString()}`
  }

  const swrValue = useSWR<{ [facetId: string]: FacetOptionDto }>(
    () => (api.isReady() ? facetOptionsApiPath + queryString : null),
    (url) => api.get(url),
    options
  );

  return {
    ...swrValue,
    isLoading: swrValue.isLoading || (!options.fallbackData && !api.isReady()),
  };
};
