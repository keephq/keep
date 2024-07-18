import { AlertDto } from "app/alerts/models";
import { IncidentDto } from "app/incidents/model";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { useWebsocket } from "./usePusher";
import { useCallback, useEffect } from "react";

export const useIncidents = (
  confirmed: boolean = true,
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<IncidentDto[]>(
    () => (session ? `${apiUrl}/incidents?confirmed=${confirmed}` : null),
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
    () => (session ? `${apiUrl}/incidents/${incidentId}/alerts` : null),
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

export const usePollIncidents = () => {
  const { bind, unbind } = useWebsocket();
  const { mutate } = useIncidents();
  const handleIncoming = useCallback(
    (data: any) => {
      console.log(data);
      mutate();
    },
    [mutate]
  );

  useEffect(() => {
    bind("incident-change", handleIncoming);
    return () => {
      unbind("incident-change", handleIncoming);
    };
  }, [bind, unbind, handleIncoming]);
};
