import {
  IncidentDto,
  IncidentsMetaDto,
  PaginatedIncidentAlertsDto,
  PaginatedIncidentsDto,
} from "@/entities/incidents/model";
import { PaginatedWorkflowExecutionDto } from "@/shared/api/workflow-executions";
import useSWR, { SWRConfiguration } from "swr";
import { useWebsocket } from "./usePusher";
import { use, useCallback, useEffect, useState } from "react";
import { useAlerts } from "@/entities/alerts/model/useAlerts";
import { useApi } from "@/shared/lib/hooks/useApi";
import { v4 as uuidv4 } from "uuid";
import {
  DEFAULT_INCIDENTS_PAGE_SIZE,
  DEFAULT_INCIDENTS_SORTING,
} from "@/entities/incidents/model/models";

interface IncidentUpdatePayload {
  incident_id: string | null;
}

export interface Filters {
  statuses?: string[];
  severities?: string[];
  assignees?: string[];
  services?: string[];
  sources?: string[];
}

export interface IncidentsQuery {
  candidate?: boolean | null;
  predicted?: boolean | null;
  limit?: number;
  offset?: number;
  sorting?: { id: string; desc: boolean };
  cel?: string;
}

function getQueryParams(query: IncidentsQuery | null): URLSearchParams | null {
  if (!query) {
    return null;
  }

  if (query.candidate === undefined) {
    // TODO: To verify if this is the correct default value
    query.candidate = true;
  }

  if (query.limit === undefined) {
    query.limit = DEFAULT_INCIDENTS_PAGE_SIZE;
  }

  if (query.offset === undefined) {
    query.offset = 0;
  }

  if (query.sorting === undefined) {
    query.sorting = DEFAULT_INCIDENTS_SORTING;
  }

  if (query.cel === undefined) {
    query.cel = "";
  }

  const filtersParams = new URLSearchParams();

  if (typeof query.candidate === "boolean") {
    filtersParams.set("candidate", query.candidate.toString());
  }

  if (query.predicted !== undefined && query.predicted !== null) {
    filtersParams.set("predicted", query.predicted.toString());
  }

  if (query.limit !== undefined) {
    filtersParams.set("limit", query.limit.toString());
  }

  if (query.offset !== undefined) {
    filtersParams.set("offset", query.offset.toString());
  }

  if (query.sorting) {
    filtersParams.set(
      "sorting",
      query.sorting.desc ? `-${query.sorting.id}` : query.sorting.id
    );
  }

  if (query.cel) {
    filtersParams.set("cel", query.cel);
  }

  return filtersParams;
}

export const useIncidents = (
  query: IncidentsQuery | null,
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  },
  trusk: boolean = false
) => {
  const filtersParams = getQueryParams(query);
  const api = useApi();

  const swrValue = useSWR(
    () =>
      api.isReady() && filtersParams
        ? `/incidents/query`
        : null,
    async (url: string) => {
      const currentDate = new Date();
      const result = await api.post(url, filtersParams ? Object.fromEntries(filtersParams) : {});
      return {
        result,
        responseTimeMs: new Date().getTime() - currentDate.getTime(),
      };
    },
    {
      ...options,
      fallbackData: {
        result: options.fallbackData,
        responseTimeMs: 0,
      },
    }
  );

  return {
    ...swrValue,
    data: swrValue.data?.result as PaginatedIncidentsDto,
    responseTimeMs: swrValue.data?.responseTimeMs,
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
    async (url: string) => api.get(url),
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
    (url: string) => api.get(url),
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
    (url: string) => api.get(url),
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
    (url: string) => api.get(url),
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

export const usePollIncidents = (mutateIncidents: any, paused: boolean = false) => {
  const { bind, unbind } = useWebsocket();
  const [incidentChangeToken, setIncidentChangeToken] = useState<
    string | undefined
  >(undefined);
  const handleIncoming = useCallback(
    (data: any) => {
      mutateIncidents();
      setIncidentChangeToken(uuidv4()); // changes every time incident change happens on the server
    },
    [mutateIncidents, setIncidentChangeToken]
  );

  useEffect(() => {
    if (paused) {
      return;
    }

    bind("incident-change", handleIncoming);
    return () => {
      unbind("incident-change", handleIncoming);
    };
  }, [bind, unbind, handleIncoming, paused]);

  return {
    incidentChangeToken,
  };
};

export const useIncidentsMeta = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();

  return useSWR<IncidentsMetaDto>(
    api.isReady() ? "/incidents/meta" : null,
    (url: string) => api.get(url),
    options
  );
};
