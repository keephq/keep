import { useState, useEffect, useMemo } from "react";
import { AlertDto } from "app/alerts/models";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { useApiUrl } from "./useConfig";
import { fetcher } from "utils/fetcher";
import { toDateObjectWithFallback } from "utils/helpers";

export type AuditEvent = {
  id: string;
  user_id: string;
  action: string;
  description: string;
  timestamp: string;
  fingerprint: string;
};

export const useAlerts = () => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  const useAlertHistory = (
    selectedAlert?: AlertDto,
    options: SWRConfiguration = { revalidateOnFocus: false }
  ) => {
    return useSWR<AlertDto[]>(
      () =>
        selectedAlert && session
          ? `${apiUrl}/alerts/${
              selectedAlert.fingerprint
            }/history?provider_id=${selectedAlert.providerId}&provider_type=${
              selectedAlert.source ? selectedAlert.source[0] : ""
            }`
          : null,
      (url) => fetcher(url, session?.accessToken),
      options
    );
  };

  const useAllAlerts = (
    presetName: string,
    options: SWRConfiguration = { revalidateOnFocus: false }
  ) => {
    return useSWR<AlertDto[]>(
      () =>
        session && presetName ? `${apiUrl}/preset/${presetName}/alerts` : null,
      (url) => fetcher(url, session?.accessToken),
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
        session && fingerprints && fingerprints?.length > 0
          ? `${apiUrl}/alerts/audit`
          : null,
      (url) =>
        fetcher(url, session?.accessToken, {
          method: "POST",
          body: JSON.stringify(fingerprints),
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session?.accessToken}`,
          },
        }),
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
        session && fingerprint ? `${apiUrl}/alerts/${fingerprint}/audit` : null,
      (url) => fetcher(url, session?.accessToken),
      options
    );
  };

  return {
    useAlertHistory,
    useAllAlerts,
    usePresetAlerts,
    useAlertAudit,
    useMultipleFingerprintsAlertAudit,
  };
};
