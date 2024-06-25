import useSWRSubscription, { SWRSubscriptionOptions } from "swr/subscription";
import Pusher, { Channel } from "pusher-js";
import { useConfig } from "./useConfig";
import { useSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";

type PusherSubscription = {
  pusherChannel: Channel | null;
  pollAlerts: number;
};

export const getDefaultSubscriptionObj = (
  pusherChannel: Channel | null = null
): PusherSubscription => ({
  pollAlerts: 0,
  pusherChannel,
});

export const usePusher = () => {
  const apiUrl = getApiURL();
  const { data: configData } = useConfig();
  const { data: session } = useSession();

  return useSWRSubscription(
    () => (configData?.PUSHER_DISABLED === false && session ? "alerts" : null),
    (_, { next }: SWRSubscriptionOptions<PusherSubscription, Error>) => {
      if (configData === undefined || session === null) {
        console.log("Pusher disabled");

        return () =>
          next(null, {
            pollAlerts: 0,
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

      pusherChannel.bind("poll-alerts", (incoming: any) => {
        next(null, (data) => {
          if (data) {
            return {
              ...data,
              pollAlerts: Math.floor(Math.random() * 10000),
            };
          }

          return {
            pollAlerts: Math.floor(Math.random() * 10000),
            isAsyncLoading: false,
            pusherChannel,
          };
        });
      });

      setTimeout(() => {
        next(null, (data) => {
          if (data) {
            return { ...data };
          }

          return {
            pollAlerts: 0,
            pusherChannel,
          };
        });
      }, 3500);

      next(null, {
        pollAlerts: 0,
        pusherChannel,
      });
      console.log("Connected to pusher");

      return () => pusher.unsubscribe(channelName);
    },
    { revalidateOnFocus: false }
  );
};
