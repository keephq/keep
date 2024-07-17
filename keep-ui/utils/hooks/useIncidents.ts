import { AlertDto } from "app/alerts/models";
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

export const useIncidentAlerts = (
  incidentId: string,
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();
  return useSWR<AlertDto[]>(
    () =>
      session ? `${apiUrl}/incidents/${incidentId}/alerts` : null,
    (url) => fetcher(url, session?.accessToken),
    options
  );
};

export const useIncident = (
  incidentId: string,
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<IncidentDto>(
    () => (session ? `${apiUrl}/incidents/${incidentId}` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
