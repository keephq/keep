import {
  IncidentDto,
  IncidentsMetaDto,
  PaginatedIncidentAlertsDto,
  PaginatedIncidentsDto,
} from "@/entities/incidents/model";
import { PaginatedWorkflowExecutionDto } from "@/app/(keep)/workflows/builder/types";
import useSWR, { SWRConfiguration } from "swr";
import { useWebsocket } from "./usePusher";
import { useCallback, useEffect } from "react";
import { useAlerts } from "./useAlerts";
import { useApi } from "@/shared/lib/hooks/useApi";

interface IncidentUpdatePayload {
  incident_id: string | null;
}

export interface Filters {
  status?: string[];
  severity?: string[];
  assignees?: string[];
  sources?: string[];
  affected_services?: string[];
}

export const useIncidents = (
  confirmed: boolean = true,
  limit: number = 25,
  offset: number = 0,
  sorting: { id: string; desc: boolean } = { id: "creation_time", desc: false },
  cel: string = "",
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();

  const filtersParams = new URLSearchParams();

  if (cel) {
    filtersParams.set("cel", cel);
  }

  const swrValue = useSWR<PaginatedIncidentsDto>(
    () =>
      api.isReady()
        ? `/incidents?confirmed=${confirmed}&limit=${limit}&offset=${offset}&sorting=${
            sorting.desc ? "-" : ""
          }${sorting.id}&${filtersParams.toString()}`
        : null,
    (url) => api.get(url),
    options
  );

  return {
    ...swrValue,
    isLoading: swrValue.isLoading || (!options.fallbackData && !api.isReady()),
  };
};

export const useIncidentAlerts = (
  incidentId: string,
  limit: number = 20,
  offset: number = 0,
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();
  return useSWR<PaginatedIncidentAlertsDto>(
    () =>
      api.isReady()
        ? `/incidents/${incidentId}/alerts?limit=${limit}&offset=${offset}`
        : null,
    (url) => api.get(url),
    options
  );
};

export const useIncidentFutureIncidents = (
  incidentId: string,
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();

  return useSWR<PaginatedIncidentsDto>(
    () => (api.isReady() ? `/incidents/${incidentId}/future_incidents` : null),
    (url) => api.get(url),
    options
  );
};

export const useIncident = (
  incidentId: string,
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();

  return useSWR<IncidentDto>(
    () => (api.isReady() && incidentId ? `/incidents/${incidentId}` : null),
    (url) => api.get(url),
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
  const api = useApi();
  return useSWR<PaginatedWorkflowExecutionDto>(
    () =>
      api.isReady()
        ? `/incidents/${incidentId}/workflows?limit=${limit}&offset=${offset}`
        : null,
    (url) => api.get(url),
    options
  );
};

export const usePollIncidentComments = (incidentId: string) => {
  const { bind, unbind } = useWebsocket();
  const { useAlertAudit } = useAlerts();
  const { mutate: mutateIncidentActivity } = useAlertAudit(incidentId);
  const handleIncoming = useCallback(
    (data: IncidentUpdatePayload) => {
      mutateIncidentActivity();
    },
    [mutateIncidentActivity]
  );
  useEffect(() => {
    bind("incident-comment", handleIncoming);
    return () => {
      unbind("incident-comment", handleIncoming);
    };
  }, [bind, unbind, handleIncoming]);
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
  const api = useApi();

  return useSWR<IncidentsMetaDto>(
    api.isReady() ? "/incidents/meta" : null,
    (url) => api.get(url),
    options
  );
};
