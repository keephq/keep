import Pusher, { Options as PusherOptions } from "pusher-js";
import { useConfig } from "./useConfig";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useApiUrl } from "./useConfig";
import { useCallback, useEffect, useRef, useState } from "react";

let PUSHER: Pusher | null = null;
const POLLING_INTERVAL = 1000 * 10; // Once per 10 seconds.

export const useWebsocket = () => {
  const apiUrl = useApiUrl();
  const { data: configData } = useConfig();
  const { data: session } = useSession();
  let channelName = `private-${session?.tenantId}`;

  console.log("useWebsocket: Initializing with config:", configData);
  console.log("useWebsocket: Session:", session);

  // TODO: should be in useMemo?
  if (
    PUSHER === null &&
    configData !== null &&
    session !== undefined &&
    configData.PUSHER_APP_KEY &&
    configData.PUSHER_DISABLED === false
  ) {
    channelName = `private-${session?.tenantId}`;
    console.log("useWebsocket: Creating new Pusher instance");
    try {
      const isRelativeHostAndNotLocal =
        configData.PUSHER_HOST &&
        !configData.PUSHER_HOST.includes("://") &&
        !["localhost", "127.0.0.1"].includes(configData.PUSHER_HOST);

      // if relative, get the relative port:
      let port = configData.PUSHER_PORT;
      if (isRelativeHostAndNotLocal) {
        port = parseInt(window.location.port, 10);
      }

      console.log(
        "useWebsocket: isRelativeHostAndNotLocal:",
        isRelativeHostAndNotLocal
      );

      var pusherOptions: PusherOptions = {
        wsHost: isRelativeHostAndNotLocal
          ? window.location.hostname
          : configData.PUSHER_HOST,
        wsPath: isRelativeHostAndNotLocal ? configData.PUSHER_HOST : "",
        wsPort: isRelativeHostAndNotLocal ? port : configData.PUSHER_PORT,
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
      };
      PUSHER = new Pusher(configData.PUSHER_APP_KEY, pusherOptions);

      console.log(
        "useWebsocket: Pusher instance created successfully. Options:",
        pusherOptions
      );

      PUSHER.connection.bind("connected", () => {
        console.log("useWebsocket: Pusher connected successfully");
      });

      PUSHER.connection.bind("error", (err: any) => {
        console.error("useWebsocket: Pusher connection error:", err);
      });

      PUSHER.connection.bind("state_change", function (states: any) {
        console.log(
          "useWebsocket: Connection state changed from",
          states.previous,
          "to",
          states.current
        );
      });

      PUSHER.subscribe(channelName)
        .bind("pusher:subscription_succeeded", () => {
          console.log(
            `useWebsocket: Successfully subscribed to ${channelName}`
          );
        })
        .bind("pusher:subscription_error", (err: any) => {
          console.error(
            `useWebsocket: Subscription error for ${channelName}:`,
            err
          );
        });
    } catch (error) {
      console.error("useWebsocket: Error creating Pusher instance:", error);
    }
  }

  const subscribe = useCallback(() => {
    console.log(`useWebsocket: Subscribing to ${channelName}`);
    return PUSHER?.subscribe(channelName);
  }, [channelName]);

  const unsubscribe = useCallback(() => {
    console.log(`useWebsocket: Unsubscribing from ${channelName}`);
    return PUSHER?.unsubscribe(channelName);
  }, [channelName]);

  const bind = useCallback(
    (event: any, callback: any) => {
      console.log(`useWebsocket: Binding to event ${event} on ${channelName}`);
      return PUSHER?.channel(channelName)?.bind(event, callback);
    },
    [channelName]
  );

  const unbind = useCallback(
    (event: any, callback: any) => {
      console.log(
        `useWebsocket: Unbinding from event ${event} on ${channelName}`
      );
      return PUSHER?.channel(channelName)?.unbind(event, callback);
    },
    [channelName]
  );

  const trigger = useCallback(
    (event: any, data: any) => {
      console.log(
        `useWebsocket: Triggering event ${event} on ${channelName} with data:`,
        data
      );
      return PUSHER?.channel(channelName).trigger(event, data);
    },
    [channelName]
  );

  const channel = useCallback(() => {
    console.log(`useWebsocket: Getting channel ${channelName}`);
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

  console.log("useAlertPolling: Initializing");

  const handleIncoming = useCallback((incoming: any) => {
    console.log("useAlertPolling: Received incoming data:", incoming);
    const currentTime = Date.now();
    const timeSinceLastPoll = currentTime - lastPollTimeRef.current;

    console.log(
      `useAlertPolling: Time since last poll: ${timeSinceLastPoll}ms`
    );

    const newPollValue = Math.floor(Math.random() * 10000);

    if (timeSinceLastPoll < POLLING_INTERVAL) {
      console.log("useAlertPolling: Ignoring poll due to short interval");
      setPollAlerts(0);
    } else {
      console.log("useAlertPolling: Updating poll alerts");
      lastPollTimeRef.current = currentTime;
      console.log(`useAlertPolling: New poll value: ${newPollValue}`);
      setPollAlerts(newPollValue);
    }
  }, []);

  useEffect(() => {
    console.log("useAlertPolling: Setting up event listener for 'poll-alerts'");
    bind("poll-alerts", handleIncoming);
    return () => {
      console.log(
        "useAlertPolling: Cleaning up event listener for 'poll-alerts'"
      );
      unbind("poll-alerts", handleIncoming);
    };
  }, [bind, unbind, handleIncoming]);

  console.log("useAlertPolling: Current poll alerts value:", pollAlerts);
  return { data: pollAlerts };
};
