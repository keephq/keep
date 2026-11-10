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
      // Normalize Pusher host, path, and port for relative paths, URLs, and host/path combinations
      let wsHost = configData.PUSHER_HOST || window.location.hostname;
      let wsPath = "";
      let wsPort = configData.PUSHER_PORT;

      if (configData.PUSHER_HOST) {
        if (configData.PUSHER_HOST.startsWith("/")) {
          // Relative path like "/websocket"
          wsHost = window.location.hostname;
          wsPath = configData.PUSHER_HOST;
          if (window.location.port) {
            wsPort = parseInt(window.location.port, 10);
          } else {
            wsPort = window.location.protocol === "https:" ? 443 : 80;
          }
        } else if (configData.PUSHER_HOST.includes("://")) {
          try {
            const parsed = new URL(configData.PUSHER_HOST);
            wsHost = parsed.hostname;
            wsPath = parsed.pathname !== "/" ? parsed.pathname : "";
            if (parsed.port) {
              wsPort = parseInt(parsed.port, 10);
            } else if (!wsPort) {
              wsPort = parsed.protocol === "https:" ? 443 : 80;
            }
          } catch {
            wsHost = configData.PUSHER_HOST;
          }
        } else if (configData.PUSHER_HOST.includes("/")) {
          // host + path e.g. "soketi-svc/websocket" or "soketi-svc:6001/websocket"
          const slashIdx = configData.PUSHER_HOST.indexOf("/");
          const hostPart = configData.PUSHER_HOST.substring(0, slashIdx);
          wsPath = configData.PUSHER_HOST.substring(slashIdx);
          if (hostPart.includes(":")) {
            const [h, p] = hostPart.split(":");
            wsHost = h;
            if (!wsPort && p) {
              wsPort = parseInt(p, 10);
            }
          } else {
            wsHost = hostPart;
          }
        } else if (configData.PUSHER_HOST.includes(":")) {
          // host + port e.g. "soketi-svc:6001"
          const [h, p] = configData.PUSHER_HOST.split(":");
          wsHost = h;
          if (!wsPort && p) {
            wsPort = parseInt(p, 10);
          }
        }
      }

      console.log("useWebsocket: wsHost:", wsHost, "wsPath:", wsPath, "wsPort:", wsPort);

      var pusherOptions: PusherOptions = {
        wsHost: wsHost,
        // in case its relative or has a path segment, use path e.g. "/websocket"
        wsPath: wsPath,
        wsPort: wsPort,
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
