import Pusher from "pusher-js";
import { useConfig } from "./useConfig";
import { useSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import { useCallback, useEffect, useRef, useState } from "react";

let PUSHER: Pusher | null = null;
const POLLING_INTERVAL = 3000;

export const useWebsocket = () => {
  const apiUrl = getApiURL();
  const { data: configData } = useConfig();
  const { data: session } = useSession();
  let channelName = `private-${session?.tenantId}`;

  if (
    PUSHER === null &&
    configData !== undefined &&
    session !== undefined &&
    configData.PUSHER_DISABLED === false
  ) {
    channelName = `private-${session?.tenantId}`;
    PUSHER = new Pusher(configData.PUSHER_APP_KEY, {
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
          Authorization: `Bearer ${session?.accessToken!}`,
        },
      },
    });
    PUSHER.subscribe(channelName);
  }

  const subscribe = () => {
    return PUSHER?.subscribe(channelName);
  };

  const unsubscribe = () => {
    return PUSHER?.unsubscribe(channelName);
  };

  const bind = (event: any, callback: any) => {
    return PUSHER?.channel(channelName)?.bind(event, callback);
  };

  const unbind = (event: any, callback: any) => {
    return PUSHER?.channel(channelName)?.unbind(event, callback);
  };

  const trigger = (event: any, data: any) => {
    return PUSHER?.channel(channelName).trigger(event, data);
  };

  const channel = () => {
    return PUSHER?.channel(channelName);
  };

  return {
    subscribe,
    unsubscribe,
    bind,
    unbind,
    trigger,
    channel,
  };
};

export const useAlertPolling = () => {
  const { bind, unbind } = useWebsocket();
  const [pollAlerts, setPollAlerts] = useState(0);
  const lastPollTimeRef = useRef(0);

  const handleIncoming = useCallback((incoming: any) => {
    const currentTime = Date.now();
    const timeSinceLastPoll = currentTime - lastPollTimeRef.current;

    if (timeSinceLastPoll < POLLING_INTERVAL) {
      setPollAlerts(0);
    } else {
      lastPollTimeRef.current = currentTime;
      setPollAlerts(Math.floor(Math.random() * 10000));
    }
  }, []);

  useEffect(() => {
    bind("poll-alerts", handleIncoming);
    return () => {
      unbind("poll-alerts", handleIncoming);
    };
  }, [bind, unbind, handleIncoming]);

  return { data: pollAlerts };
};
