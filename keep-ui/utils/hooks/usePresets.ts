import { useState, useEffect, useRef } from "react";
import { Preset } from "app/alerts/models";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { useConfig } from "./useConfig";
import useSWRSubscription from "swr/subscription";
import { useWebsocket } from "./usePusher";
import { useSearchParams } from "next/navigation";
import moment from "moment";

export const usePresets = (type?: string, useFilters?: boolean) => {
  const { data: session } = useSession();
  const { data: configData } = useConfig();
  const apiUrl = getApiURL();
  const isDashBoard = type === 'dashboard'
  const presetType = isDashBoard ? `${type}__` : "" + "presets-order";;
  const [presetsOrderFromLS, setPresetsOrderFromLS] = useLocalStorage<Preset[]>(
    "presets-order",
    []
  );
  const [dashboardPresetsOrderFromLS, setDashboardPresetsOrderFromLS] = useLocalStorage<Preset[]>(
    presetType,
    []
  )

  const searchParams = useSearchParams();

  const [staticPresetsOrderFromLS, setStaticPresetsOrderFromLS] =
    useLocalStorage<Preset[]>(`static-presets-order`, []);
  const [staticDashboardPresetsOrderFromLS, setStaticDashPresetsOrderFromLS] =
    useLocalStorage<Preset[]>(`static-${presetType}`, []);
  // used to sync the presets with the server
  const [isLocalStorageReady, setIsLocalStorageReady] = useState(false);
  const [isDashboardLocalStorageReady, setIsDashboardLocalStorageReady] = useState(false);
  const presetsOrderRef = useRef(presetsOrderFromLS);
  const dashboradPresetsOrderRef = useRef(dashboardPresetsOrderFromLS);
  const staticPresetsOrderRef = useRef(staticPresetsOrderFromLS);
  const dashboardStaticPresetsOrderRef = useRef(staticDashboardPresetsOrderFromLS);
  const { bind, unbind } = useWebsocket();

  useEffect(() => {
    presetsOrderRef.current = presetsOrderFromLS;
    staticPresetsOrderRef.current = staticPresetsOrderFromLS;
  }, [presetsOrderFromLS, staticPresetsOrderFromLS]);

  useEffect(() => {
    if (isDashBoard) {
      dashboradPresetsOrderRef.current = dashboardPresetsOrderFromLS;
      dashboardStaticPresetsOrderRef.current = staticDashboardPresetsOrderFromLS;
    }
  }, [type, dashboardPresetsOrderFromLS, staticDashboardPresetsOrderFromLS]);

  const updateLocalPresets = (newPresets: Preset[]) => {
    const updatePresets = (currentPresets: Preset[], newPresets: Preset[]) => {
      const newPresetMap = new Map(newPresets.map((p) => [p.id, p]));
      let updatedPresets = new Map(currentPresets.map((p) => [p.id, p]));

      newPresetMap.forEach((newPreset, newPresetId) => {
        const currentPreset = updatedPresets.get(newPresetId);
        if (currentPreset) {
          // Update existing preset with new alerts count
          updatedPresets.set(newPresetId, {
            ...currentPreset,
            alerts_count: currentPreset.alerts_count + newPreset.alerts_count,
            created_by: newPreset.created_by,
            is_private: newPreset.is_private
          }); 
        } else {
          // If the preset is not in the current presets, add it
          updatedPresets.set(newPresetId, {
            ...newPreset,
            alerts_count: newPreset.alerts_count,
          });
        }
      });

      return Array.from(updatedPresets.values());
    };
    const time_stamp = searchParams?.get('time_stamp');
    let endDate = null;
    try {
      endDate = time_stamp ? JSON.parse(time_stamp)?.end : null;
    } catch (err) {
      //do nothing
    }
    const startOfToday = moment().startOf('day')
    //let say the filter we have applied is before today. then the recent changes should not be applied
    if ((isDashBoard && endDate && startOfToday.isAfter(moment(endDate)))) {
      setDashboardPresetsOrderFromLS((current) =>
        updatePresets(
          dashboradPresetsOrderRef.current,
          newPresets.filter(
            (p) => !["feed", "deleted", "dismissed", "groups"].includes(p.name)
          )
        )
      );
      setStaticPresetsOrderFromLS((current) =>
        updatePresets(
          dashboardStaticPresetsOrderRef.current,
          newPresets.filter((p) =>
            ["feed", "deleted", "dismissed", "groups"].includes(p.name)
          )
        )
      );
    }

    setPresetsOrderFromLS((current) =>
      updatePresets(
        presetsOrderRef.current,
        newPresets.filter(
          (p) => !["feed", "deleted", "dismissed", "groups"].includes(p.name)
        )
      )
    );
    setStaticPresetsOrderFromLS((current) =>
      updatePresets(
        staticPresetsOrderRef.current,
        newPresets.filter((p) =>
          ["feed", "deleted", "dismissed", "groups"].includes(p.name)
        )
      )
    );
  };

  useSWRSubscription(
    () =>
      configData?.PUSHER_DISABLED === false && session && (isLocalStorageReady || isDashboardLocalStorageReady)
        ? "presets"
        : null,
    (_, { next }) => {
      const newPresets = (newPresets: Preset[]) => {
        updateLocalPresets(newPresets);
        next(null, {
          presets: newPresets,
          isAsyncLoading: false,
          lastSubscribedDate: new Date(),
        });
      };

      bind("async-presets", newPresets);

      return () => {
        console.log("Unbinding from presets channel");
        unbind("async-presets", newPresets);
      };
    },
    { revalidateOnFocus: false }
  );

  const useFetchAllPresets = (options?: SWRConfiguration) => {
    const filters = searchParams?.toString()
    return useSWR<Preset[]>(
      () => (session ? `${apiUrl}/preset${(useFilters && filters && isDashBoard) ? `?${filters}` : ''}` : null),
      (url) => fetcher(url, session?.accessToken),
      {
        ...options,
        onSuccess: (data) => {
          if (data) {
            const dynamicPresets = data.filter(
              (p) =>
                !["feed", "deleted", "dismissed", "groups"].includes(p.name)
            );
            const staticPresets = data.filter((p) =>
              ["feed", "deleted", "dismissed", "groups"].includes(p.name)
            );

            const dashboardDynamicPresets = data.filter(
              (p) =>
                !["feed", "deleted", "dismissed", "groups"].includes(p.name));
            const staticDashboardPresets = data.filter((p) =>
              ["feed", "deleted", "dismissed", "groups"].includes(p.name));

            if (isDashBoard) {
              mergePresetsWithLocalStorage(
                dashboardDynamicPresets,
                dashboardPresetsOrderFromLS,
                setDashboardPresetsOrderFromLS,
                type,
              );
              mergePresetsWithLocalStorage(
                staticDashboardPresets,
                staticDashboardPresetsOrderFromLS,
                setStaticDashPresetsOrderFromLS,
                type
              );
            } else {
              mergePresetsWithLocalStorage(
                dynamicPresets,
                presetsOrderFromLS,
                setPresetsOrderFromLS
              );
              mergePresetsWithLocalStorage(
                staticPresets,
                staticPresetsOrderFromLS,
                setStaticPresetsOrderFromLS
              );
            }
          }
        },
      }
    );
  };

  const mergePresetsWithLocalStorage = (
    serverPresets: Preset[],
    localPresets: Preset[],
    setter: (presets: Preset[]) => void,
    type?: string
  ) => {
    // This map quickly checks presence by ID
    const serverPresetIds = new Set(serverPresets.map((sp) => sp.id));

    // Filter localPresets to remove those not present in serverPresets
    const updatedLocalPresets = localPresets
      .filter((lp) => serverPresetIds.has(lp.id))
      .map((lp) => {
        // Find the server version of this local preset
        const serverPreset = serverPresets.find((sp) => sp.id === lp.id);
        // If found, merge, otherwise just return local (though filtered above)
        return serverPreset ? { ...lp, ...serverPreset } : lp;
      });

    // Filter serverPresets to find those not in local storage, to add new presets from server
    const newServerPresets = serverPresets.filter(
      (sp) => !localPresets.some((lp) => lp.id === sp.id)
    );

    // Combine the updated local presets with any new server presets
    const combinedPresets = updatedLocalPresets.concat(newServerPresets);

    // Update state with combined list
    setter(combinedPresets);
    if (isDashBoard) {
      setIsDashboardLocalStorageReady(true);
    } else {
      setIsLocalStorageReady(true);
    }
  };

  const useAllPresets = (options?: SWRConfiguration) => {
    const {
      data: presets,
      error,
      isValidating,
      mutate,
    } = useFetchAllPresets(options);
    const filteredPresets = presets?.filter(
      (preset) =>
        !["feed", "deleted", "dismissed", "groups"].includes(preset.name)
    );
    return {
      data: filteredPresets,
      error,
      isValidating,
      mutate,
    };
  };

  const useStaticPresets = (options?: SWRConfiguration) => {
    const {
      data: presets,
      error,
      isValidating,
      mutate,
    } = useFetchAllPresets(options);
    const staticPresets = presets?.filter((preset) =>
      ["feed", "deleted", "dismissed", "groups"].includes(preset.name)
    );
    return {
      data: staticPresets,
      error,
      isValidating,
      mutate,
    };
  };

  return {
    useAllPresets,
    useStaticPresets,
    presetsOrderFromLS,
    setPresetsOrderFromLS,
    staticPresetsOrderFromLS,
    dashboardPresetsOrderFromLS,
    setDashboardPresetsOrderFromLS,
    dashboardStaticPresetsOrderRef
  };
};
