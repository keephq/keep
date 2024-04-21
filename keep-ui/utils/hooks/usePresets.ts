import { useState, useEffect, useRef, useCallback } from "react";
import { Preset } from "app/alerts/models";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import Pusher, {Channel} from "pusher-js";
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
            ...newPreset,
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

  const subscription = useSWRSubscription(
    () => (configData?.PUSHER_DISABLED === false && session && isLocalStorageReady) ? "presets" : null,
    (_, { next }) => {
      console.log("Subscribing to presets channel")
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
            Authorization: `Bearer ${session.accessToken}`
          },
        },
      });

      const channelName = `private-${session.tenantId}`;
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

  const mergePresetsWithLocalStorage = (serverPresets, localPresets, setter) => {
    const updatedLocalPresets = localPresets.map(lp => {
        const serverPreset = serverPresets.find(sp => sp.id === lp.id);
        return serverPreset ? {...lp, ...serverPreset} : lp;
    });

    const newServerPresets = serverPresets.filter(sp => !localPresets.some(lp => lp.id === sp.id));
    const combinedPresets = updatedLocalPresets.concat(newServerPresets);
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
