import { useEffect, useState } from "react";
import { useWebsocket } from "@/utils/hooks/usePusher";
import { Observable } from "rxjs";
import { v4 as generateGuid } from "uuid";

type PollAlertsPayload = {
  fingerprints?: string[];
};

export function parsePollAlertsPayload(data: unknown): string[] {
  if (!data) {
    return [];
  }

  let payload: unknown = data;
  if (typeof data === "string") {
    try {
      payload = JSON.parse(data);
    } catch {
      return [];
    }
  }

  if (
    typeof payload === "object" &&
    payload !== null &&
    "fingerprints" in payload
  ) {
    const fingerprints = (payload as PollAlertsPayload).fingerprints;
    if (!Array.isArray(fingerprints)) {
      return [];
    }

    return fingerprints.filter(
      (fingerprint): fingerprint is string =>
        typeof fingerprint === "string" && fingerprint.length > 0
    );
  }

  return [];
}

export const useAlertPolling = (isEnabled: boolean) => {
  const { bind, unbind } = useWebsocket();
  const [data, setData] = useState<string | null>(null);
  const [fingerprints, setFingerprints] = useState<string[]>([]);

  useEffect(() => {
    if (!isEnabled) {
      return;
    }

    const subscription = new Observable<unknown>((subscriber) => {
      const callback = (eventData: unknown) => subscriber.next(eventData);
      bind("poll-alerts", callback);
      return () => unbind("poll-alerts", callback);
    }).subscribe((eventData) => {
      setData(generateGuid());
      setFingerprints(parsePollAlertsPayload(eventData));
    });

    return () => subscription.unsubscribe();
  }, [isEnabled, bind, unbind]);

  return { data, fingerprints };
};
