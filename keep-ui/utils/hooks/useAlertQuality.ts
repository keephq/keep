import { useSession } from "next-auth/react";
import { getApiURL } from "../apiUrl";
import { SWRConfiguration } from "swr";
import { fetcher } from "../fetcher";
import useSWRImmutable from "swr/immutable";
import { useSearchParams } from "next/navigation";

export const useAlertQualityMetrics = (options: SWRConfiguration = {}) => {
  const { data: session } = useSession();
  const apiUrl = getApiURL();
  const searchParams = useSearchParams();
  const filters = searchParams?.toString();

  // TODO: Proper type needs to be defined.
  return useSWRImmutable<Record<string, Record<string, any>>>(
    () => (session ? `${apiUrl}/alerts/quality/metrics${filters?.length ? `?${filters}` : ""}` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
