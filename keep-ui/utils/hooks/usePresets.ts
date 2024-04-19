import { Preset } from "app/alerts/models";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { useLocalStorage } from "utils/hooks/useLocalStorage";

export const usePresets = () => {
  const { data: session } = useSession();
  const apiUrl = getApiURL();

  const [presetsOrderFromLS, setPresetsOrderFromLS] = useLocalStorage<Preset[]>("presets-order", []);
  const [staticPresetsOrderFromLS, setStaticPresetsOrderFromLS] = useLocalStorage<Preset[]>("static-presets-order", []);

  const useFetchAllPresets = (options?: SWRConfiguration) => {
    return useSWR<Preset[]>(
      () => (session ? `${apiUrl}/preset` : null),
      url => fetcher(url, session?.accessToken),
      {
        ...options,
        refreshInterval: 25000,
        onSuccess: (data) => {
          if (data) {
            const dynamicPresets = data.filter(p => !['feed', 'deleted', 'dismissed', 'groups'].includes(p.name));
            const staticPresets = data.filter(p => ['feed', 'deleted', 'dismissed', 'groups'].includes(p.name));
            mergePresetsWithLocalStorage(dynamicPresets, presetsOrderFromLS, setPresetsOrderFromLS);
            mergePresetsWithLocalStorage(staticPresets, staticPresetsOrderFromLS, setStaticPresetsOrderFromLS);
          }
        }
      }
    );
  };

  const mergePresetsWithLocalStorage = (serverPresets, localPresets, setter) => {
    // Start by mapping over local presets to retain order and update details
    const updatedLocalPresets = localPresets.map(lp => {
        // Find the corresponding server preset to update details
        const serverPreset = serverPresets.find(sp => sp.id === lp.id);
        return serverPreset ? {...lp, ...serverPreset} : lp;
    });

    // Include any new presets from the server that aren't already in the local storage
    const newServerPresets = serverPresets.filter(sp => !localPresets.some(lp => lp.id === sp.id));

    // Combine the updated local presets with any new server presets
    const combinedPresets = updatedLocalPresets.concat(newServerPresets);

    // Update the local storage with the combined list
    setter(combinedPresets);
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

  return { useAllPresets, useStaticPresets, presetsOrderFromLS, setPresetsOrderFromLS, staticPresetsOrderFromLS };
};
