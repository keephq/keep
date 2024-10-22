import useSWR from "swr";
import { useSession } from "next-auth/react";
import { useApiUrl } from "./useConfig";
import { fetcher } from "utils/fetcher";

export interface Dashboard {
  id: string;
  dashboard_name: string;
  dashboard_config: any;
}

export const useDashboards = () => {
  const { data: session } = useSession();
  const apiUrl = useApiUrl();

  const { data, error, mutate } = useSWR<Dashboard[]>(
    session ? `${apiUrl}/dashboard` : null,
    (url: string) => fetcher(url, session!.accessToken),
    {
      revalidateOnFocus: false,
    }
  );

  return {
    dashboards: data,
    error,
    isLoading: !data && !error,
    mutate,
  };
};
