import { useState, useEffect, useRef } from "react";
import { Preset } from "app/alerts/models";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import Pusher from "pusher-js";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { useConfig } from "./useConfig";
import useSWRSubscription from "swr/subscription";

export const usePresets = () => {
  const { data: session } = useSession();
  const { data: configData } = useConfig();
  const apiUrl = getApiURL();

  const [presetsOrderFromLS, setPresetsOrderFromLS] = useLocalStorage<Preset[]>("presets-order", []);
  const [staticPresetsOrderFromLS, setStaticPresetsOrderFromLS] = useLocalStorage<Preset[]>("static-presets-order", []);
  // used to sync the presets with the server
  const [isLocalStorageReady, setIsLocalStorageReady] = useState(false);
  const presetsOrderRef = useRef(presetsOrderFromLS);
  const staticPresetsOrderRef = useRef(staticPresetsOrderFromLS);

  useEffect(() => {
    presetsOrderRef.current = presetsOrderFromLS;
    staticPresetsOrderRef.current = staticPresetsOrderFromLS;
  }, [presetsOrderFromLS, staticPresetsOrderFromLS]);

  const updateLocalPresets = (newPresets: Preset[]) => {
    const updatePresets = (currentPresets: Preset[], newPresets: Preset[]) => {
      const newPresetMap = new Map(newPresets.map(p => [p.id, p]));
      let updatedPresets = new Map(currentPresets.map(p => [p.id, p]));

      newPresetMap.forEach((newPreset, newPresetId) => {
        const currentPreset = updatedPresets.get(newPresetId);
        if (currentPreset) {
          // Update existing preset with new alerts count
          updatedPresets.set(newPresetId, {
            ...currentPreset,
            alerts_count: currentPreset.alerts_count + newPreset.alerts_count
          });
        } else {
          // If the preset is not in the current presets, add it
          updatedPresets.set(newPresetId, {
            ...newPreset,
            alerts_count: newPreset.alerts_count
          });
        }
      });

      return Array.from(updatedPresets.values());
    };

    setPresetsOrderFromLS(current => updatePresets(presetsOrderRef.current, newPresets.filter(p => !['feed', 'deleted', 'dismissed', 'groups'].includes(p.name))));
    setStaticPresetsOrderFromLS(current => updatePresets(staticPresetsOrderRef.current, newPresets.filter(p => ['feed', 'deleted', 'dismissed', 'groups'].includes(p.name))));
  };

  useSWRSubscription(
    () => (configData?.PUSHER_DISABLED === false && session && isLocalStorageReady) ? "presets" : null,
    (_, { next }) => {
      console.log("Subscribing to presets channel")
      const pusher = new Pusher(configData!.PUSHER_APP_KEY, {
        wsHost: configData!.PUSHER_HOST,
        wsPort: configData!.PUSHER_PORT,
        forceTLS: false,
        disableStats: true,
        enabledTransports: ["ws", "wss"],
        cluster: configData!.PUSHER_CLUSTER || "local",
        channelAuthorization: {
          transport: "ajax",
          endpoint: `${apiUrl}/pusher/auth`,
          headers: {
            Authorization: `Bearer ${session!.accessToken}`
          },
        },
      });

      const channelName = `private-${session!.tenantId}`;
      const channel = pusher.subscribe(channelName);

      channel.bind("async-presets", (newPresets: Preset[]) => {
        console.log("Received new presets from server", newPresets);
        updateLocalPresets(newPresets);
        next(null, {
          presets: newPresets,
          isAsyncLoading: false,
          lastSubscribedDate: new Date(),
          pusherChannel: channel
        });
      });

      return () => {
        console.log("Unsubscribing from presets channel")
        pusher.unsubscribe(channelName);
      };
    },
    { revalidateOnFocus: false }
  );


  const useFetchAllPresets = (options?: SWRConfiguration) => {
    return useSWR<Preset[]>(
      () => (session ? `${apiUrl}/preset` : null),
      url => fetcher(url, session?.accessToken),
      {
        ...options,
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

  const mergePresetsWithLocalStorage = (serverPresets: Preset[], localPresets: Preset[], setter: (presets: Preset[]) => void) => {
    // This map quickly checks presence by ID
    const serverPresetIds = new Set(serverPresets.map(sp => sp.id));

    // Filter localPresets to remove those not present in serverPresets
    const updatedLocalPresets = localPresets.filter(lp => serverPresetIds.has(lp.id)).map(lp => {
        // Find the server version of this local preset
        const serverPreset = serverPresets.find(sp => sp.id === lp.id);
        // If found, merge, otherwise just return local (though filtered above)
        return serverPreset ? {...lp, ...serverPreset} : lp;
    });

    // Filter serverPresets to find those not in local storage, to add new presets from server
    const newServerPresets = serverPresets.filter(sp => !localPresets.some(lp => lp.id === sp.id));

    // Combine the updated local presets with any new server presets
    const combinedPresets = updatedLocalPresets.concat(newServerPresets);

    // Update state with combined list
    setter(combinedPresets);
    setIsLocalStorageReady(true);
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
