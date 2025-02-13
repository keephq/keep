import { useEffect, useState } from "react";
import { useWebsocket } from "@/utils/hooks/usePusher";
import { Observable, throttleTime } from "rxjs";
import { v4 as generateGuid } from "uuid";

const ALERT_POLLING_INTERVAL = 1000 * 2; // Once per 5 seconds.

export const useAlertPolling = (isEnabled: boolean) => {
  const { bind, unbind } = useWebsocket();
  const [pollAlerts, setPollAlerts] = useState<string | null>(null);

  console.log("useAlertPolling: Initializing");

  useEffect(() => {
    if (!isEnabled) {
      console.log("useAlertPolling: Disabling polling");
      return;
    }

    const subscription = new Observable((subscriber) => {
      const callback = () => subscriber.next();
      bind("poll-alerts", callback);
      return () => unbind("poll-alerts", callback);
    })
      .pipe(throttleTime(ALERT_POLLING_INTERVAL))
      .subscribe(() => setPollAlerts(generateGuid()));
    return () => subscription.unsubscribe();
  }, [isEnabled, bind, unbind]);

  return { data: pollAlerts };
};
