import { useState, useEffect } from "react";
import { Preset } from "app/alerts/models";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import Pusher from "pusher-js";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { useConfig } from "./useConfig";

export const usePresets = () => {
  const { data: session } = useSession();
  const { data: configData } = useConfig();
  const apiUrl = getApiURL();

  const [presetsOrderFromLS, setPresetsOrderFromLS] = useLocalStorage<Preset[]>("presets-order", []);
  const [staticPresetsOrderFromLS, setStaticPresetsOrderFromLS] = useLocalStorage<Preset[]>("static-presets-order", []);

  const updateLocalPresets = (newPresets: Preset[]) => {
    // Helper function to update presets
    const updatePresets = (currentPresets: Preset[], newPresets: Preset[]) => {
      const presetMap = new Map(currentPresets.map(p => [p.id, p]));

      newPresets.forEach(newPreset => {
        const existingPreset = presetMap.get(newPreset.id);
        if (existingPreset) {
          // Update alerts count or any other properties that are expected to change
          existingPreset.alerts_count = (existingPreset.alerts_count || 0) + (newPreset.alerts_count || 0);
        } else {
          // Add new preset if not already in the map
          presetMap.set(newPreset.id, newPreset);
        }
      });

      return Array.from(presetMap.values());
    };

    // Update non-static presets
    setPresetsOrderFromLS(currentPresets => updatePresets(currentPresets, newPresets.filter(p => !['feed', 'deleted', 'dismissed', 'groups'].includes(p.name))));

    // Update static presets
    setStaticPresetsOrderFromLS(currentPresets => updatePresets(currentPresets, newPresets.filter(p => ['feed', 'deleted', 'dismissed', 'groups'].includes(p.name))));
  };

  useEffect(() => {
    if (!session || configData?.PUSHER_DISABLED) return;

    const pusher = new Pusher(configData.PUSHER_APP_KEY, {
      wsHost: configData.PUSHER_HOST,
      wsPort: configData.PUSHER_PORT,
      forceTLS: false,
      disableStats: true,
      enabledTransports: ["ws", "wss"],
      cluster: configData.PUSHER_CLUSTER || "local",
      channelAuthorization: {
        transport: "ajax",
        endpoint: `${apiUrl}/pusher/auth`,
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
        },
      },
    });

    const channelName = `private-${session.tenantId}`;
    const channel = pusher.subscribe(channelName);

    channel.bind("async-presets", (newPresets: Preset[]) => {
      // Logic to handle incoming preset data
      console.log("Received new presets via Pusher", newPresets);
      // iterate over the new presets and update the local storage
      // we need to iterate the new preset and add preset.alerts_count to the current
      updateLocalPresets(newPresets);
    });

    return () => {
      pusher.unsubscribe(channelName);
    };
  }, [session, configData, updateLocalPresets]);


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
    const updatedLocalPresets = localPresets.map(lp => {
        const serverPreset = serverPresets.find(sp => sp.id === lp.id);
        return serverPreset ? {...lp, ...serverPreset} : lp;
    });

    const newServerPresets = serverPresets.filter(sp => !localPresets.some(lp => lp.id === sp.id));
    const combinedPresets = updatedLocalPresets.concat(newServerPresets);
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
