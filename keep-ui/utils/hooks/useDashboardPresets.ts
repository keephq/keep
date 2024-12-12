import { usePresets } from "./usePresets";
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
