import { useSession } from "next-auth/react";
import { getApiURL } from "../apiUrl";
import { SWRConfiguration } from "swr";
import { fetcher } from "../fetcher";
import useSWRImmutable from "swr/immutable";

export const useAlertQualityMetrics = (options: SWRConfiguration = {}) => {
  const { data: session } = useSession();
  const apiUrl = getApiURL();

  // TODO: Proper type needs to be defined.
  return useSWRImmutable<Record<string, Record<string, any>>>(
    () => (session ? `${apiUrl}/alerts/quality/metrics` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
