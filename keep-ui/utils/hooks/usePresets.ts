import { Preset } from "app/alerts/models";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const usePresets = () => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  const useFetchAllPresets = (options?: SWRConfiguration) => {
    const apiUrl = getApiURL();
    const { data: session } = useSession();

    return useSWR<Preset[]>(
      () => (session ? `${apiUrl}/preset` : null),
      url => fetcher(url, session?.accessToken),
      { ...options, refreshInterval: 25000 }
    );
  };

  const useAllPresets = (options?: SWRConfiguration) => {
    const { data: presets, error, isValidating, mutate } = useFetchAllPresets(options);

    const filteredPresets = presets?.filter(preset => !['feed', 'deleted', 'dismissed', 'groups'].includes(preset.name));

    return {
      data: filteredPresets,
      error,
      isValidating,
      mutate,
    };
  };
  const useStaticPresets = (options?: SWRConfiguration) => {
    const { data: presets, error, isValidating, mutate } = useFetchAllPresets(options);

    const staticPresets = presets?.filter(preset => ['feed', 'deleted', 'dismissed', 'groups'].includes(preset.name));

    return {
      data: staticPresets,
      error,
      isValidating,
      mutate,
    };
  };

  return { useAllPresets, useStaticPresets};
};
