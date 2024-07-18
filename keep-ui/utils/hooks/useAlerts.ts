import { useState, useEffect } from "react";
import { AlertDto } from "app/alerts/models";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { toDateObjectWithFallback } from "utils/helpers";

export const useAlerts = () => {
  const apiUrl = getApiURL();
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
            }/history/?provider_id=${selectedAlert.providerId}&provider_type=${
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
      () => (session && presetName ? `${apiUrl}/preset/${presetName}/alerts` : null),
      (url) => fetcher(url, session?.accessToken),
      options
    );
  };

  const usePresetAlerts = (
    presetName: string,
    options: SWRConfiguration = { revalidateOnFocus: false }
  ) => {
    const [alertsMap, setAlertsMap] = useState<Map<string, AlertDto>>(
      new Map()
    );

    const {
      data: alertsFromEndpoint = [],
      mutate,
      isLoading,
    } = useAllAlerts(presetName, options);

    useEffect(() => {
      if (alertsFromEndpoint.length) {
        const newAlertsMap = new Map<string, AlertDto>(
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

        setAlertsMap(newAlertsMap);
      }
    }, [alertsFromEndpoint]);

    return {
      data: Array.from(alertsMap.values()),
      mutate: mutate,
      isLoading: isLoading,
    };
  };

  const useAlertAudit = (
    fingerprint: string,
    options: SWRConfiguration = { revalidateOnFocus: false }
  ) => {
    return useSWR(
      () => (session && fingerprint ? `${apiUrl}/alerts/${fingerprint}/audit` : null),
      (url) => fetcher(url, session?.accessToken),
      options
    );
  };

  return {
    useAlertHistory,
    useAllAlerts,
    usePresetAlerts,
    useAlertAudit
  };
};
