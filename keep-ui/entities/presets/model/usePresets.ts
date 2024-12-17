import useSWR, { SWRConfiguration } from "swr";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { useConfig } from "@/utils/hooks/useConfig";
import useSWRSubscription from "swr/subscription";
import { useWebsocket } from "@/utils/hooks/usePusher";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useMemo, useCallback } from "react";
import isEqual from "lodash/isEqual";
import { Session } from "next-auth";
import {
  LOCAL_PRESETS_KEY,
  LOCAL_STATIC_PRESETS_KEY,
  STATIC_PRESETS_NAMES,
} from "@/entities/presets/model/constants";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";
import { Preset } from "@/entities/presets/model/types";
import { useHydratedSession } from "@/shared/lib/hooks/useHydratedSession";
import debounce from "lodash.debounce";

type UsePresetsOptions = {
  filters?: string;
} & SWRConfiguration;

// debounce the revalidation of the presets to avoid too many requests to the server
const DEBOUNCE_TIME = 2000;

const checkPresetAccess = (preset: Preset, session: Session) => {
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

export const usePresets = ({ filters, ...options }: UsePresetsOptions = {}) => {
  const api = useApi();
  const { data: configData } = useConfig();
  const { data: session } = useHydratedSession();
  const [localDynamicPresets, setLocalDynamicPresets] = useLocalStorage<
    Preset[]
  >(LOCAL_PRESETS_KEY, []);
  const [localStaticPresets, setLocalStaticPresets] = useLocalStorage<Preset[]>(
    LOCAL_STATIC_PRESETS_KEY,
    []
  );

  const { bind, unbind } = useWebsocket();
  const revalidateMultiple = useRevalidateMultiple();

  // Create a debounced revalidate function
  const debouncedRevalidate = useMemo(
    () =>
      debounce(() => {
        revalidateMultiple(["/preset"], { isExact: true });
      }, DEBOUNCE_TIME),
    [revalidateMultiple]
  );

  useSWRSubscription(
    () =>
      configData?.PUSHER_DISABLED === false && api.isReady() ? "presets" : null,
    (_, { next }) => {
      const handleIncoming = (presetNamesToUpdate: string[]) => {
        debouncedRevalidate();
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
        debouncedRevalidate.cancel();
      };
    },
    { revalidateOnFocus: false }
  );

  const updateLocalPresets = useCallback(
    (presets: Preset[]) => {
      if (!session) {
        return;
      }
      // TODO: if the new preset coming from the server is not in the local storage, add it to the local storage
      // Keep the order from the local storage, update the data from the server
      const newDynamicPresets = combineOrder(
        presets
          .filter((preset) => !STATIC_PRESETS_NAMES.includes(preset.name))
          .filter((preset) => checkPresetAccess(preset, session)),
        localDynamicPresets
      );
      // Only update if the array actually changed
      if (!isEqual(newDynamicPresets, localDynamicPresets)) {
        setLocalDynamicPresets(newDynamicPresets);
      }
      const newStaticPresets = combineOrder(
        presets
          .filter((preset) => STATIC_PRESETS_NAMES.includes(preset.name))
          .filter((preset) => checkPresetAccess(preset, session)),
        localStaticPresets
      );
      if (!isEqual(newStaticPresets, localStaticPresets)) {
        setLocalStaticPresets(newStaticPresets);
      }
    },
    [
      localDynamicPresets,
      localStaticPresets,
      session,
      setLocalDynamicPresets,
      setLocalStaticPresets,
    ]
  );

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
      onSuccess: updateLocalPresets,
      ...options,
    }
  );

  const dynamicPresets = useMemo(() => {
    if (error) {
      return [];
    }
    if (!allPresets || !session) {
      return localDynamicPresets;
    }
    const dynamicPresets = allPresets
      .filter((preset) => !STATIC_PRESETS_NAMES.includes(preset.name))
      .filter((preset) => checkPresetAccess(preset, session));
    return combineOrder(dynamicPresets, localDynamicPresets);
  }, [allPresets, error, localDynamicPresets, session]);

  const staticPresets = useMemo(() => {
    if (error) {
      return [];
    }
    if (!allPresets) {
      return localStaticPresets;
    }
    const staticPresets = allPresets.filter((preset) =>
      STATIC_PRESETS_NAMES.includes(preset.name)
    );
    return combineOrder(staticPresets, localStaticPresets);
  }, [allPresets, error, localStaticPresets]);

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
