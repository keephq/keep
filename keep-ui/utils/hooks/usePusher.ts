import Pusher from "pusher-js";
import { useConfig } from "./useConfig";
import { useSession } from "next-auth/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

let PUSHER: Pusher | null = null;
const POLLING_INTERVAL = 3000;

export const useWebsocket = () => {
  const { data: configData } = useConfig();
  const { data: session } = useSession();
  const [error, setError] = useState<string | null>(null);

  const channelName = useMemo(() => {
    return session?.tenantId ? `private-${session.tenantId}` : null;
  }, [session?.tenantId]);

  useEffect(() => {
    if (
      PUSHER === null &&
      configData &&
      session &&
      channelName &&
      !configData.PUSHER_DISABLED
    ) {
      try {
        PUSHER = new Pusher(configData.PUSHER_APP_KEY, {
          cluster: configData.PUSHER_CLUSTER || "local",
          forceTLS: true,
          authEndpoint: "/api/pusher/auth",
          auth: {
            headers: {
              Authorization: `Bearer ${session.accessToken}`,
            },
          },
          wsHost: window.location.hostname,
          wsPort: window.location.port
            ? parseInt(window.location.port)
            : window.location.protocol === "https:"
            ? 443
            : 80,
          wssPort: window.location.port
            ? parseInt(window.location.port)
            : window.location.protocol === "https:"
            ? 443
            : 80,
          enabledTransports: ["ws", "wss"],
          disabledTransports: ["xhr_streaming", "xhr_polling", "sockjs"],
        });
        PUSHER.subscribe(channelName);
      } catch (err) {
        setError(`Failed to initialize Pusher: ${(err as Error).message}`);
      }
    }

    return () => {
      if (PUSHER && channelName) {
        PUSHER.unsubscribe(channelName);
        PUSHER.disconnect();
        PUSHER = null;
      }
    };
  }, [configData, session, channelName]);

  const subscribe = useCallback(() => {
    if (PUSHER && channelName) {
      return PUSHER.subscribe(channelName);
    }
  }, [channelName]);

  const unsubscribe = useCallback(() => {
    if (PUSHER && channelName) {
      return PUSHER.unsubscribe(channelName);
    }
  }, [channelName]);

  const bind = useCallback(
    (event: string, callback: (data: any) => void) => {
      if (PUSHER && channelName) {
        return PUSHER.channel(channelName)?.bind(event, callback);
      }
    },
    [channelName]
  );

  const unbind = useCallback(
    (event: string, callback: (data: any) => void) => {
      if (PUSHER && channelName) {
        return PUSHER.channel(channelName)?.unbind(event, callback);
      }
    },
    [channelName]
  );

  const trigger = useCallback(
    (event: string, data: any) => {
      if (PUSHER && channelName) {
        return PUSHER.channel(channelName)?.trigger(event, data);
      }
    },
    [channelName]
  );

  return {
    subscribe,
    unsubscribe,
    bind,
    unbind,
    trigger,
    error,
  };
};

export const useAlertPolling = () => {
  const { bind, unbind, error } = useWebsocket();
  const [pollAlerts, setPollAlerts] = useState(0);
  const lastPollTimeRef = useRef(0);

  const handleIncoming = useCallback(() => {
    const currentTime = Date.now();
    const timeSinceLastPoll = currentTime - lastPollTimeRef.current;

    if (timeSinceLastPoll >= POLLING_INTERVAL) {
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

  return { data: pollAlerts, error };
};
