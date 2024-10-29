import Pusher from "pusher-js";
import { useConfig } from "./useConfig";
import { useSession } from "next-auth/react";
import { useApiUrl } from "./useConfig";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

let PUSHER: Pusher | null = null;
const POLLING_INTERVAL = 3000;

export const useWebsocket = () => {
  const apiUrl = useApiUrl();
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
    try {
      const isRelativeHost =
        configData.PUSHER_HOST && !configData.PUSHER_HOST.includes("://");
      PUSHER = new Pusher(configData.PUSHER_APP_KEY, {
        wsHost: isRelativeHost
          ? window.location.hostname
          : configData.PUSHER_HOST,
        wsPath: isRelativeHost ? configData.PUSHER_HOST : "",
        wsPort: isRelativeHost
          ? window.location.protocol === "https:"
            ? 443
            : 80
          : configData.PUSHER_PORT,
        forceTLS: window.location.protocol === "https:",
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
    } catch (error) {
      console.error("useWebsocket: Error creating Pusher instance:", error);
    }
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

  const channel = useCallback(() => {
    return PUSHER?.channel(channelName);
  }, [channelName]);

  return {
    subscribe,
    unsubscribe,
    bind,
    unbind,
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
      const newPollValue = Math.floor(Math.random() * 10000);
      setPollAlerts(newPollValue);
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
