import {
  IncidentDto,
  IncidentsMetaDto,
  PaginatedIncidentAlertsDto,
  PaginatedIncidentsDto,
} from "../../app/incidents/models";
import { PaginatedWorkflowExecutionDto } from "app/workflows/builder/types";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { useWebsocket } from "./usePusher";
import { useCallback, useEffect } from "react";

interface IncidentUpdatePayload {
  incident_id: string | null;
}

interface Filters {
  status: string[];
  severity: string[];
  assignees: string[];
  sources: string[];
  affected_services: string[];
}

export const useIncidents = (
  confirmed: boolean = true,
  limit: number = 25,
  offset: number = 0,
  sorting: { id: string; desc: boolean } = { id: "creation_time", desc: false },
  filters: Filters | {} = {},
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  const filtersParams = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value.length == 0) {
      filtersParams.delete(key as string);
    } else {
      value.forEach((s: string) => {
        filtersParams.append(key, s);
      });
    }
  });

  return useSWR<PaginatedIncidentsDto>(
    () =>
      session
        ? `${apiUrl}/incidents?confirmed=${confirmed}&limit=${limit}&offset=${offset}&sorting=${
            sorting.desc ? "-" : ""
          }${sorting.id}&${filtersParams.toString()}`
        : null,
    (url) => fetcher(url, session?.accessToken),
    options
  );
};

export const useIncidentAlerts = (
  incidentId: string,
  limit: number = 20,
  offset: number = 0,
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();
  return useSWR<PaginatedIncidentAlertsDto>(
    () =>
      session
        ? `${apiUrl}/incidents/${incidentId}/alerts?limit=${limit}&offset=${offset}`
        : null,
    (url) => fetcher(url, session?.accessToken),
    options
  );
};

export const useIncidentFutureIncidents = (
  incidentId: string,
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<PaginatedIncidentsDto>(
    () =>
      session ? `${apiUrl}/incidents/${incidentId}/future_incidents` : null,
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
    () => (session && incidentId ? `${apiUrl}/incidents/${incidentId}` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};

export const useIncidentWorkflowExecutions = (
  incidentId: string,
  limit: number = 20,
  offset: number = 0,
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();
  return useSWR<PaginatedWorkflowExecutionDto>(
    () =>
      session
        ? `${apiUrl}/incidents/${incidentId}/workflows?limit=${limit}&offset=${offset}`
        : null,
    (url) => fetcher(url, session?.accessToken),
    options
  );
};

export const usePollIncidentAlerts = (incidentId: string) => {
  const { bind, unbind } = useWebsocket();
  const { mutate } = useIncidentAlerts(incidentId);
  const handleIncoming = useCallback(
    (data: IncidentUpdatePayload) => {
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

export const usePollIncidents = (mutateIncidents: any) => {
  const { bind, unbind } = useWebsocket();
  const handleIncoming = useCallback(
    (data: any) => {
      mutateIncidents();
    },
    [mutateIncidents]
  );

  useEffect(() => {
    bind("incident-change", handleIncoming);
    return () => {
      unbind("incident-change", handleIncoming);
    };
  }, [bind, unbind, handleIncoming]);
};

export const useIncidentsMeta = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  return useSWR<IncidentsMetaDto>(
    () => (session ? `${apiUrl}/incidents/meta` : null),
    (url) => fetcher(url, session?.accessToken),
    options
  );
};
