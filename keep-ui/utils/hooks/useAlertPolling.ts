import { useCallback, useEffect, useRef, useState } from "react";
import { useWebsocket } from "@/utils/hooks/usePusher";

const ALERT_POLLING_INTERVAL = 1000 * 10; // Once per 10 seconds.

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

    if (timeSinceLastPoll < ALERT_POLLING_INTERVAL) {
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
