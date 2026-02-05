"use client";

import { useApiUrl, useConfig } from "./useConfig";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useCallback, useEffect, useRef } from "react";

type EventSourceRef = {
  source: EventSource | null;
  handlers: Map<string, Set<(data: string) => void>>;
};

let sharedRef: EventSourceRef | null = null;

function getOrCreateEventSource(
  url: string,
  handlers: Map<string, Set<(data: string) => void>>
): EventSource | null {
  if (sharedRef?.source?.readyState === EventSource.OPEN) {
    return sharedRef.source;
  }
  if (sharedRef?.source) {
    sharedRef.source.close();
    sharedRef = null;
  }
  try {
    const source = new EventSource(url);
    sharedRef = { source, handlers };

    source.addEventListener("connected", (e: MessageEvent) => {
      handlers.get("connected")?.forEach((cb) => cb(e.data));
    });
    source.addEventListener("heartbeat", () => {
      handlers.get("heartbeat")?.forEach((cb) => cb(""));
    });
    source.addEventListener("poll-alerts", (e: MessageEvent) => {
      handlers.get("poll-alerts")?.forEach((cb) => cb(e.data));
    });
    source.addEventListener("incident-change", (e: MessageEvent) => {
      handlers.get("incident-change")?.forEach((cb) => cb(e.data));
    });
    source.addEventListener("poll-presets", (e: MessageEvent) => {
      handlers.get("poll-presets")?.forEach((cb) => cb(e.data));
    });
    source.addEventListener("topology-update", (e: MessageEvent) => {
      handlers.get("topology-update")?.forEach((cb) => cb(e.data));
    });
    source.addEventListener("ai-logs-change", (e: MessageEvent) => {
      handlers.get("ai-logs-change")?.forEach((cb) => cb(e.data));
    });
    source.addEventListener("incident-comment", (e: MessageEvent) => {
      handlers.get("incident-comment")?.forEach((cb) => cb(e.data));
    });
    source.addEventListener("alert-update", (e: MessageEvent) => {
      handlers.get("alert-update")?.forEach((cb) => cb(e.data));
    });

    source.onerror = () => {
      // EventSource auto-reconnects; log only if closed
      if (source.readyState === EventSource.CLOSED) {
        console.error("useSSE: EventSource closed");
      }
    };

    return source;
  } catch (err) {
    console.error("useSSE: Failed to create EventSource", err);
    return null;
  }
}

/**
 * SSE-based real-time hook. Replaces useWebsocket (Pusher).
 * Supports no-auth: when no session or PUSHER_DISABLED, connection uses default tenant or is disabled.
 */
export const useSSE = () => {
  const apiUrl = useApiUrl();
  const { data: configData } = useConfig();
  const { data: session } = useSession();
  const handlersRef = useRef<Map<string, Set<(data: string) => void>>>(new Map());

  const sseUrl =
    apiUrl &&
    configData !== null &&
    configData.PUSHER_DISABLED === false
      ? `${apiUrl.replace(/\/$/, "")}/sse/events${
          session?.accessToken
            ? `?token=${encodeURIComponent(session.accessToken)}`
            : ""
        }`
      : null;

  useEffect(() => {
    if (!sseUrl) return;
    const handlers = handlersRef.current;
    getOrCreateEventSource(sseUrl, handlers);
  }, [sseUrl]);

  const bind = useCallback((event: string, callback: (data: string) => void) => {
    const handlers = handlersRef.current;
    if (!handlers.has(event)) {
      handlers.set(event, new Set());
    }
    handlers.get(event)!.add(callback);
  }, []);

  const unbind = useCallback((event: string, callback: (data: string) => void) => {
    handlersRef.current.get(event)?.delete(callback);
  }, []);

  const subscribe = useCallback(() => {
    if (sseUrl && sharedRef?.source?.readyState !== EventSource.OPEN) {
      getOrCreateEventSource(sseUrl, handlersRef.current);
    }
  }, [sseUrl]);

  const unsubscribe = useCallback(() => {
    if (sharedRef?.source) {
      sharedRef.source.close();
      sharedRef = null;
    }
  }, []);

  const trigger = useCallback((_event: string, _data: unknown) => {
    // Client does not push events to SSE; no-op for API compatibility
  }, []);

  const channel = useCallback(() => null, []);

  return {
    subscribe,
    unsubscribe,
    bind,
    unbind,
    trigger,
    channel,
  };
};
