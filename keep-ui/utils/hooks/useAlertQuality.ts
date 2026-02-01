import { SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import { useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";

export const useAlertQualityMetrics = (
  fields: string | string[],
  options: SWRConfiguration = {}
) => {
  const api = useApi();
  const searchParams = useSearchParams();
  const filters = useMemo(() => {
    const params = new URLSearchParams(searchParams?.toString() || "");
    if (fields) {
      const fieldArray = Array.isArray(fields) ? fields : [fields];
      fieldArray.forEach((field) => params.append("fields", field));
    }

    return params.toString();
  }, [fields, searchParams]);
  // TODO: Proper type needs to be defined.
  return useSWRImmutable<Record<string, Record<string, any>>>(
    () =>
      api.isReady()
        ? `/alerts/quality/metrics${filters ? `?${filters}` : ""}`
        : null,
    (url) => api.get(url),
    options
  );
};
