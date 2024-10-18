import { useSession } from "next-auth/react";
import { getApiURL } from "../apiUrl";
import { SWRConfiguration } from "swr";
import { fetcher } from "../fetcher";
import useSWRImmutable from "swr/immutable";
import { useSearchParams } from "next/navigation";
import { useMemo } from "react";

export const useAlertQualityMetrics = (
  fields: string | string[],
  options: SWRConfiguration = {}
) => {
  const { data: session } = useSession();
  const apiUrl = getApiURL();
  const searchParams = useSearchParams();
  ``;
  let filters = useMemo(() => {
    let params = searchParams?.toString();
    if (fields) {
      fields = Array.isArray(fields) ? fields : [fields];
      let fieldParams = new URLSearchParams("");
      fields.forEach((field) => {
        fieldParams.append("fields", field);
      });
      params = params
        ? `${params}&${fieldParams.toString()}`
        : fieldParams.toString();
    }
    return params;
  }, [fields?.toString(), searchParams?.toString()]);
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
