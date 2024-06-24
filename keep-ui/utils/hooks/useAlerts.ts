import { useState, useEffect } from "react";
import { AlertDto } from "app/alerts/models";
import { useSession } from "next-auth/react";
import Pusher, { Channel } from "pusher-js";
import useSWR, { SWRConfiguration } from "swr";
import useSWRSubscription, { SWRSubscriptionOptions } from "swr/subscription";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { useConfig } from "./useConfig";
import { toDateObjectWithFallback } from "utils/helpers";

type AlertSubscription = {
  alerts: AlertDto[];
  lastSubscribedDate: Date;
  isAsyncLoading: boolean;
  pusherChannel: Channel | null;
};

const convertAlertsToMap = (alerts: AlertDto[]): Map<string, AlertDto> => {
  const alertsMap = new Map<string, AlertDto>();
  alerts.forEach((alert) => {
    alertsMap.set(alert.fingerprint, {
      ...alert,
      lastReceived: toDateObjectWithFallback(alert.lastReceived),
    });
  });
  return alertsMap;
};

const getFormatAndMergePusherWithEndpointAlerts = (
  alertsMap: Map<string, AlertDto>,
  newPusherAlerts: AlertDto[]
) =>
  newPusherAlerts.reduce((newAlertsMap, alertFromPusher) => {
    const existingAlert = newAlertsMap.get(alertFromPusher.fingerprint);

    if (existingAlert) {
      if (alertFromPusher.lastReceived >= existingAlert.lastReceived) {
        newAlertsMap.set(alertFromPusher.fingerprint, alertFromPusher);
      }
    } else {
      newAlertsMap.set(alertFromPusher.fingerprint, alertFromPusher);
    }

    return newAlertsMap;
  }, new Map(alertsMap));

export const getDefaultSubscriptionObj = (
  isAsyncLoading: boolean = false,
  pusherChannel: Channel | null = null
): AlertSubscription => ({
  alerts: [],
  isAsyncLoading,
  lastSubscribedDate: new Date(),
  pusherChannel,
});

export const useAlerts = () => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();
  const { data: configData } = useConfig();

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
      () => (configData && session ? "alerts" : null),
      () =>
        fetcher(
          `${apiUrl}/preset/${presetName}/alerts?sync=${
            configData?.PUSHER_DISABLED ? "true" : "false"
          }`,
          session?.accessToken
        ),
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

    const { data: alertsFromEndpoint = [], ...restOfAllAlerts } = useAllAlerts(
      presetName,
      options
    );

    const { data: alertSubscription = getDefaultSubscriptionObj() } =
      useAlertsFromPusher();
    const { alerts: alertsFromPusher, ...restOfAlertSubscription } =
      alertSubscription;

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

    useEffect(() => {
      if (alertsFromPusher.length) {
        const alertsFromPusherWithLastReceivedDate = alertsFromPusher.map(
          (alertFromPusher) => ({
            ...alertFromPusher,
            lastReceived: toDateObjectWithFallback(
              alertFromPusher.lastReceived
            ),
          })
        );

        setAlertsMap((previousAlertsMap) =>
          getFormatAndMergePusherWithEndpointAlerts(
            previousAlertsMap,
            alertsFromPusherWithLastReceivedDate
          )
        );
      }
    }, [alertsFromPusher]);

    return {
      data: Array.from(alertsMap.values()),
      ...restOfAlertSubscription,
      ...restOfAllAlerts,
    };
  };

  const useAlertsFromPusher = () => {
    return useSWRSubscription(
      () =>
        configData?.PUSHER_DISABLED === false && session ? "alerts" : null,
      (_, { next }: SWRSubscriptionOptions<AlertSubscription, Error>) => {
        if (configData === undefined || session === null) {
          console.log("Pusher disabled");

          return () =>
            next(null, {
              alerts: [],
              isAsyncLoading: false,
              lastSubscribedDate: new Date(),
              pusherChannel: null,
            });
        }

        console.log("Connecting to pusher");
        const pusher = new Pusher(configData.PUSHER_APP_KEY, {
          wsHost: configData.PUSHER_HOST,
          wsPort: configData.PUSHER_PORT,
          forceTLS: false,
          disableStats: true,
          enabledTransports: ["ws", "wss"],
          cluster: configData.PUSHER_CLUSTER || "local",
          channelAuthorization: {
            transport: "ajax",
            endpoint: `${apiUrl}/pusher/auth`,
            headers: {
              Authorization: `Bearer ${session.accessToken!}`,
            },
          },
        });

        const channelName = `private-${session.tenantId}`;
        const pusherChannel = pusher.subscribe(channelName);

        pusherChannel.bind("async-alerts", (newAlerts: AlertDto[]) => {
          next(null, (data) => {
            if (data) {
              return {
                ...data,
                alerts: newAlerts,
              };
            }

            return {
              alerts: newAlerts,
              lastSubscribedDate: new Date(),
              isAsyncLoading: false,
              pusherChannel,
            };
          });
        });

        pusherChannel.bind("async-done", () => {
          next(null, (data) => {
            if (data) {
              return { ...data, isAsyncLoading: false };
            }

            return {
              alerts: [],
              lastSubscribedDate: new Date(),
              isAsyncLoading: false,
              pusherChannel,
            };
          });
        });

        setTimeout(() => {
          next(null, (data) => {
            if (data) {
              return { ...data, isAsyncLoading: false };
            }

            return {
              alerts: [],
              lastSubscribedDate: new Date(),
              isAsyncLoading: false,
              pusherChannel,
            };
          });
        }, 3500);

        next(null, {
          alerts: [],
          lastSubscribedDate: new Date(),
          isAsyncLoading: true,
          pusherChannel,
        });
        console.log("Connected to pusher");

        return () => pusher.unsubscribe(channelName);
      },
      { revalidateOnFocus: false }
    );
  };

  return {
    useAlertHistory,
    useAllAlerts,
    useAlertsFromPusher,
    usePresetAlerts,
  };
};
