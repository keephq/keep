import { usePresets } from "@/entities/presets/model/usePresets";
import { useSearchParams } from "next/navigation";

export const useDashboardPreset = () => {
  const searchParams = useSearchParams();

  const { dynamicPresets, staticPresets } = usePresets({
    filters: searchParams?.toString(),
    revalidateIfStale: false,
    revalidateOnFocus: false,
  });

  return [...staticPresets, ...dynamicPresets];
};
