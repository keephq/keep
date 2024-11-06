import useSWR from "swr";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
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
