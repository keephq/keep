import { Preset } from "@/app/(keep)/alerts/models";
import useSWR, { SWRConfiguration } from "swr";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { useConfig } from "./useConfig";
import useSWRSubscription from "swr/subscription";
import { useWebsocket } from "./usePusher";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useRevalidateMultiple } from "../state";
import { useHydratedSession } from "@/shared/lib/hooks/useHydratedSession";
import { useMemo } from "react";
const STATIC_PRESETS = ["feed"];

type UsePresetsOptions = {
  filters?: string;
} & SWRConfiguration;

export const usePresets = ({ filters, ...options }: UsePresetsOptions = {}) => {
  const api = useApi();
  const { data: session } = useHydratedSession();
  const { data: configData } = useConfig();
  const [localDynamicPresets, setLocalDynamicPresets] = useLocalStorage<
    Preset[]
  >("presets-order", []);
  const [localStaticPresets, setLocalStaticPresets] = useLocalStorage<Preset[]>(
    "static-presets-order",
    []
  );

  const { bind, unbind } = useWebsocket();
  const revalidateMultiple = useRevalidateMultiple();

  useSWRSubscription(
    () =>
      configData?.PUSHER_DISABLED === false && api.isReady() ? "presets" : null,
    (_, { next }) => {
      const handleIncoming = (presetNamesToUpdate: string[]) => {
        revalidateMultiple(["/preset"], { isExact: true });
        next(null, {
          presetNamesToUpdate,
          isAsyncLoading: false,
          lastSubscribedDate: new Date(),
        });
      };

      bind("poll-presets", handleIncoming);

      return () => {
        console.log("Unbinding from presets channel");
        unbind("poll-presets", handleIncoming);
      };
    },
    { revalidateOnFocus: false }
  );

  const updateLocalPresets = (presets: Preset[]) => {
    // Keep the order from the local storage, update the data from the server
    setLocalDynamicPresets(
      localDynamicPresets
        .filter((preset) => !STATIC_PRESETS.includes(preset.name))
        .map((preset) => {
          const presetFromData = presets.find((p) => p.id === preset.id);
          return presetFromData ? { ...preset, ...presetFromData } : null;
        })
        .filter((preset) => preset !== null) as Preset[]
    );
    setLocalStaticPresets(
      localStaticPresets
        .filter((preset) => STATIC_PRESETS.includes(preset.name))
        .map((preset) => {
          const presetFromData = presets.find((p) => p.id === preset.id);
          return presetFromData ? { ...preset, ...presetFromData } : null;
        })
        .filter((preset) => preset !== null) as Preset[]
    );
  };

  const checkValidPreset = (preset: Preset) => {
    if (!preset.is_private) {
      return true;
    }
    return preset && preset.created_by == session?.user?.email;
  };

  const combineOrder = (serverPresets: Preset[], localPresets: Preset[]) => {
    // If the preset is in local, update it with the server data
    // If the preset is not in local, add it
    // If the preset is in local and not in server, remove it
    const addedPresetsMap = new Map<string, boolean>();
    const orderedPresets = localPresets
      .map((preset) => {
        const presetFromData = serverPresets.find((p) => p.id === preset.id);
        addedPresetsMap.set(preset.id, !!presetFromData);
        return presetFromData ? presetFromData : null;
      })
      .filter((preset) => preset !== null) as Preset[];
    const serverPresetsNotInLocal = serverPresets.filter(
      (preset) => !addedPresetsMap.get(preset.id)
    );
    return [...orderedPresets, ...serverPresetsNotInLocal];
  };

  const {
    data: allPresets,
    isLoading,
    error,
    isValidating,
    mutate,
  } = useSWR<Preset[]>(
    api.isReady() ? `/preset${filters ? `?${filters}` : ""}` : null,
    (url) => api.get(url),
    {
      onSuccess: (data) => {
        updateLocalPresets(data);
      },
      ...options,
    }
  );

  const dynamicPresets = useMemo(() => {
    if (!allPresets) {
      return localDynamicPresets;
    }
    const dynamicPresets = allPresets.filter(
      (preset) => !STATIC_PRESETS.includes(preset.name)
    );
    return combineOrder(dynamicPresets, localDynamicPresets);
  }, [allPresets, localDynamicPresets]);
  const staticPresets = useMemo(() => {
    if (!allPresets) {
      return localStaticPresets;
    }
    const staticPresets = allPresets.filter((preset) =>
      STATIC_PRESETS.includes(preset.name)
    );
    return combineOrder(staticPresets, localStaticPresets);
  }, [allPresets, localStaticPresets]);

  return {
    dynamicPresets,
    staticPresets,
    isLoading,
    error,
    isValidating,
    mutate,
    setLocalDynamicPresets,
  };
};
