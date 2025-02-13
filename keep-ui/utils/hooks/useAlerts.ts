import { useMemo } from "react";
import { AlertDto } from "@/entities/alerts/model";
import useSWR, { SWRConfiguration } from "swr";
import { toDateObjectWithFallback } from "utils/helpers";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";

export type AuditEvent = {
  id: string;
  user_id: string;
  action: string;
  description: string;
  timestamp: string;
  fingerprint: string;
};

export interface AlertsQuery {
  cel?: string;
  offset?: number;
  limit?: number;
  sortBy?: string;
  sortDirection?: "ASC" | "DESC";
}

export const useAlerts = () => {
  const api = useApi();
  const revalidateMultiple = useRevalidateMultiple();
  const alertsMutator = () => revalidateMultiple(["/alert"]);

  const useAlertHistory = (
    selectedAlert?: AlertDto,
    options: SWRConfiguration = { revalidateOnFocus: false }
  ) => {
    return useSWR<AlertDto[]>(
      () =>
        api.isReady() && selectedAlert
          ? `/alerts/${
              selectedAlert.fingerprint
            }/history?provider_id=${selectedAlert.providerId}&provider_type=${
              selectedAlert.source ? selectedAlert.source[0] : ""
            }`
          : null,
      (url) => api.get(url),
      options
    );
  };

  const useAllAlerts = (
    presetName: string,
    options: SWRConfiguration = { revalidateOnFocus: false }
  ) => {
    return useSWR<AlertDto[]>(
      () =>
        api.isReady() && presetName ? `/preset/${presetName}/alerts` : null,
      (url) => api.get(url),
      options
    );
  };

  const usePresetAlerts = (
    presetName: string,
    options: SWRConfiguration = { revalidateOnFocus: false }
  ) => {
    const {
      data: alertsFromEndpoint = [],
      mutate,
      isLoading,
      error: alertsError,
    } = useAllAlerts(presetName, options);

    const alertsValue = useMemo(() => {
      if (!alertsFromEndpoint.length) {
        return [];
      }

      const alertsMap = new Map<string, AlertDto>(
        alertsFromEndpoint.map((alertFromEndpoint) => [
          alertFromEndpoint.fingerprint,
          {
            ...alertFromEndpoint,
            lastReceived: toDateObjectWithFallback(
              alertFromEndpoint.lastReceived
            ),
          },
        ])
      );
      return Array.from(alertsMap.values());
    }, [alertsFromEndpoint]);

    return {
      data: [],
      mutate: mutate,
      isLoading: isLoading,
      error: alertsError,
    };
  };

  const useMultipleFingerprintsAlertAudit = (
    fingerprints: string[] | undefined,
    options: SWRConfiguration = {
      revalidateOnFocus: false,
    }
  ) => {
    return useSWR<AuditEvent[]>(
      () =>
        api.isReady() && fingerprints && fingerprints?.length > 0
          ? `/alerts/audit`
          : null,
      (url) => api.post(url, fingerprints),
      options
    );
  };

  const useAlertAudit = (
    fingerprint: string,
    options: SWRConfiguration = {
      revalidateOnFocus: false,
    }
  ) => {
    return useSWR<AuditEvent[]>(
      () =>
        api.isReady() && fingerprint ? `/alerts/${fingerprint}/audit` : null,
      (url) => api.get(url),
      options
    );
  };

  const useLastAlerts = (
    query: AlertsQuery | undefined,
    options: SWRConfiguration = { revalidateOnFocus: false }
  ) => {
    const filtersParams = new URLSearchParams();

    if (query?.offset !== undefined) {
      filtersParams.set("offset", String(query.offset));
    }

    if (query?.limit !== undefined) {
      filtersParams.set("limit", String(query.limit));
    }

    if (query?.cel) {
      filtersParams.set("cel", query.cel);
    }

    if (query?.sortBy) {
      filtersParams.set("sort_by", query.sortBy);

      switch (query?.sortDirection) {
        case "DESC":
          filtersParams.set("sort_dir", "desc");
          break;
        default:
          filtersParams.set("sort_dir", "asc");
      }
    }

    let requestUrl = `/alerts/query`;

    if (filtersParams.toString()) {
      requestUrl += `?${filtersParams.toString()}`;
    }

    const swrValue = useSWR<any>(
      () => (api.isReady() && query ? requestUrl : null),
      () => api.get(requestUrl),
      options
    );

    return {
      ...swrValue,
      data: swrValue.data?.results as AlertDto[],
      isLoading: swrValue.isLoading || !swrValue.data,
      totalCount: swrValue.data?.count,
      limit: swrValue.data?.limit,
      offset: swrValue.data?.offset,
    };
  };

  return {
    useAlertHistory,
    useAllAlerts,
    usePresetAlerts,
    useAlertAudit,
    useMultipleFingerprintsAlertAudit,
    useLastAlerts,
    alertsMutator,
  };
};
