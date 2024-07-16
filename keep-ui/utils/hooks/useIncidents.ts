import { IncidentDto } from "app/incidents/model";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useIncidents = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<IncidentDto[]>(
    () => (session ? `${apiUrl}/incidents` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
