import Pusher, { Options as PusherOptions } from "pusher-js";
import { useApiUrl, useConfig } from "./useConfig";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useCallback } from "react";

let PUSHER: Pusher | null = null;

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
      // check if the pusher host is relative (e.g. /websocket)
      const isRelative =
        configData.PUSHER_HOST && configData.PUSHER_HOST.startsWith("/");

      // if relative, get the relative port:
      let port = configData.PUSHER_PORT;
      if (isRelative) {
        // Handle case where port is empty string (default ports 80/443)
        if (window.location.port) {
          port = parseInt(window.location.port, 10);
        } else {
          // Use default ports based on protocol
          port = window.location.protocol === "https:" ? 443 : 80;
        }
      }

      console.log("useWebsocket: isRelativeHostAndNotLocal:", isRelative);

      var pusherOptions: PusherOptions = {
        wsHost: isRelative ? window.location.hostname : configData.PUSHER_HOST,
        // in case its relative, use path e.g. "/websocket"
        wsPath: isRelative ? configData.PUSHER_HOST : "",
        wsPort: isRelative ? port : configData.PUSHER_PORT,
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
        void err; // No-op line for debugger target
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
