import { useEffect, useMemo } from "react";
import { AlertDto } from "@/entities/alerts/model";
import useSWR, { SWRConfiguration } from "swr";
import { toDateObjectWithFallback } from "utils/helpers";
import { useApi } from "@/shared/lib/hooks/useApi";

export type AuditEvent = {
  id: string;
  user_id: string;
  action: string;
  description: string;
  timestamp: string;
  fingerprint: string;
};

export const useAlerts = () => {
  const api = useApi();

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
      data: alertsValue,
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
    cel: string,
    limit: number,
    offset: number,
    options: SWRConfiguration = { revalidateOnFocus: false }
  ) => {
    const filtersParams = new URLSearchParams();

    if (offset !== undefined) {
      filtersParams.set("offset", String(offset));
    }

    if (limit !== undefined) {
      filtersParams.set("limit", String(limit));
    }

    if (cel) {
      filtersParams.set("cel", cel);
    }

    let requestUrl = `/alerts`;

    if (filtersParams.toString()) {
      requestUrl += `?${filtersParams.toString()}`;
    }

    const swrValue = useSWR<any>(
      () =>
        api.isReady() ? requestUrl : null,
      (url) => api.get(url),
      options
    );

    return {
      ...swrValue,
      data: swrValue.data?.results as AlertDto[],
      totalCount: swrValue.data?.count,
      limit: swrValue.data?.limit,
      offset: swrValue.data?.offset
    };
  };

  return {
    useAlertHistory,
    useAllAlerts,
    usePresetAlerts,
    useAlertAudit,
    useMultipleFingerprintsAlertAudit,
    useLastAlerts
  };
};
