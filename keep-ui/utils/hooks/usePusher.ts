import Pusher from "pusher-js";
import { useConfig } from "./useConfig";
import { useSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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
      wsHost: configData.PUSHER_HOST || window.location.hostname,
      wsPort: configData.PUSHER_PORT
        ? configData.PUSHER_PORT
        : window.location.protocol === "https:"
        ? 443
        : 80,
      forceTLS: window.location.protocol === "https:",
      disableStats: true,
      enabledTransports: ["ws", "wss"],
      cluster: configData.PUSHER_CLUSTER || "local",
      ...(configData.PUSHER_PREFIX && { wsPath: configData.PUSHER_PREFIX }),
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

  const subscribe = useCallback(() => {
    return PUSHER?.subscribe(channelName);
  }, [channelName]);

  const unsubscribe = useCallback(() => {
    return PUSHER?.unsubscribe(channelName);
  }, [channelName]);

  const bind = useCallback(
    (event: any, callback: any) => {
      return PUSHER?.channel(channelName)?.bind(event, callback);
    },
    [channelName]
  );

  const unbind = useCallback(
    (event: any, callback: any) => {
      return PUSHER?.channel(channelName)?.unbind(event, callback);
    },
    [channelName]
  );

  const trigger = useCallback(
    (event: any, data: any) => {
      return PUSHER?.channel(channelName).trigger(event, data);
    },
    [channelName]
  );

  const channel = useCallback(() => {
    return PUSHER?.channel(channelName);
  }, [channelName]);

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
