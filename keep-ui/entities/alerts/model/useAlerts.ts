import { useEffect, useMemo, useState } from "react";
import { AlertDto, AlertsQuery, AuditEvent } from "./types";
import useSWR, { SWRConfiguration } from "swr";
import { toDateObjectWithFallback } from "@/utils/helpers";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";

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
          ? `/alerts/${selectedAlert.fingerprint}/history?provider_id=${
              selectedAlert.providerId
            }&provider_type=${
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

  const useErrorAlerts = (
    options: SWRConfiguration = { revalidateOnFocus: false }
  ) => {
    const { data, error, isLoading, mutate } = useSWR<any>(
      () => (api.isReady() ? `/alerts/event/error` : null),
      (url) => api.get(url),
      options
    );

    // Consolidated function to dismiss error alerts
    // If alertId is provided, dismisses that specific alert
    // If no alertId is provided, dismisses all alerts
    const dismissErrorAlerts = async (alertId?: string) => {
      if (!api.isReady()) return false;

      try {
        const payload = alertId ? { alert_id: alertId } : {};
        await api.post(`/alerts/event/error/dismiss`, payload);
        await mutate(); // Refresh the data
        return true;
      } catch (error) {
        console.error("Failed to dismiss error alert(s):", error);
        return false;
      }
    };

    return {
      data,
      error,
      isLoading,
      mutate,
      dismissErrorAlerts,
    };
  };

  const useLastAlerts = (
    query: AlertsQuery | undefined,
    options: SWRConfiguration = { revalidateOnFocus: false }
  ) => {
    const queryToPost: { [key: string]: any } = {};

    if (query?.offset !== undefined) {
      queryToPost.offset = query.offset;
    }

    if (query?.limit !== undefined) {
      queryToPost.limit = query.limit;
    }

    if (query?.cel) {
      queryToPost.cel = query.cel;
    }

    if (query?.sortOptions?.length) {
      queryToPost.sort_options = query.sortOptions.map((sortOption) => ({
        sort_by: sortOption.sortBy,
        sort_dir: sortOption.sortDirection?.toLocaleLowerCase(),
      }));
    }

    const requestUrl = `/alerts/query`;
    const swrKey = () =>
      // adding "/alerts/query" so global revalidation works
      api.isReady() && query
        ? requestUrl +
          Object.entries(queryToPost)
            .sort(([fstKey], [scdKey]) => fstKey.localeCompare(scdKey))
            .map(([key, value]) => `${key}=${JSON.stringify(value)}`)
            .join("&")
        : null;

    const swrValue = useSWR<any>(
      swrKey,
      async () => {
        const date = new Date();
        const queryResult = await api.post(requestUrl, queryToPost);
        const queryTimeInSeconds =
          (new Date().getTime() - date.getTime()) / 1000;
        return {
          queryResult,
          queryTimeInSeconds,
        };
      },
      options
    );

    const [results, setResults] = useState<AlertDto[]>([]);

    useEffect(() => {
      if (swrValue.isLoading) {
        return;
      }

      setResults(swrValue.data?.queryResult?.results || []);
    }, [swrValue.data, swrValue.isLoading]);

    return {
      ...swrValue,
      data: results,
      queryTimeInSeconds: swrValue.data?.queryTimeInSeconds,
      isLoading: swrValue.isLoading || !swrValue.data?.queryResult,
      totalCount: swrValue.data?.queryResult?.count as number,
      limit: swrValue.data?.queryResult?.limit as number,
      offset: swrValue.data?.queryResult?.offset as number,
    };
  };

  return {
    useAlertHistory,
    useAllAlerts,
    usePresetAlerts,
    useAlertAudit,
    useMultipleFingerprintsAlertAudit,
    useErrorAlerts,
    useLastAlerts,
    alertsMutator,
  };
};
