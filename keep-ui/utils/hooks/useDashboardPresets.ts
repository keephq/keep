import { useSession } from "next-auth/react";
import { usePresets } from "./usePresets";
import { Preset } from "@/app/(keep)/alerts/models";
import { useMemo } from "react";
import { useSearchParams } from "next/navigation";

export const useDashboardPreset = () => {
  const { data: session } = useSession();

  const {
    useAllPresets,
    useStaticPresets,
    presetsOrderFromLS,
    staticPresetsOrderFromLS,
  } = usePresets("dashboard", true);
  const { data: presets = [] } = useAllPresets({
    revalidateIfStale: false,
    revalidateOnFocus: false,
  });
  const { data: fetchedPresets = [] } = useStaticPresets({
    revalidateIfStale: false,
  });
  const searchParams = useSearchParams();

  const checkValidPreset = (preset: Preset) => {
    if (!preset.is_private) {
      return true;
    }
    return preset && preset.created_by == session?.user?.email;
  };

  let allPreset = useMemo(() => {
    /*If any filters are applied on the dashboard, we will fetch live data; otherwise,
    we will use data from localStorage to sync values between the navbar and the dashboard.*/
    let combinedPresets = searchParams?.toString()
      ? [...presets, ...fetchedPresets]
      : [...presetsOrderFromLS, ...staticPresetsOrderFromLS];
    //private preset checks
    combinedPresets = combinedPresets.filter((preset) =>
      checkValidPreset(preset)
    );
    return combinedPresets;
  }, [presets, fetchedPresets, searchParams, presets, fetchedPresets]);

  return allPreset;
};
