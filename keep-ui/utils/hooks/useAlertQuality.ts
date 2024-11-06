import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { SWRConfiguration } from "swr";
import { fetcher } from "../fetcher";
import useSWRImmutable from "swr/immutable";
import { useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { useApiUrl } from "./useConfig";

export const useAlertQualityMetrics = (
  fields: string | string[],
  options: SWRConfiguration = {}
) => {
  const { data: session } = useSession();
  const apiUrl = useApiUrl();
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
      session
        ? `${apiUrl}/alerts/quality/metrics${filters ? `?${filters}` : ""}`
        : null,
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
