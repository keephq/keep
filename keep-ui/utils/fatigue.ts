import { AlertDto } from "@/app/alerts/models";

const WINDOW_SIZE = 60 * 60 * 1000; // 60 minutes in milliseconds
const MAX_ALERTS_PER_WINDOW = 50; // This number might come from historical data or whatever we decide

export const calculateFatigue = (
  alerts: AlertDto[],
  timeUnit: string = "hours"
): any[] => {
  let windowSize = WINDOW_SIZE;
  let maxAlertsPerWindow = MAX_ALERTS_PER_WINDOW;
  if (timeUnit.toLowerCase() === "minutes") {
    windowSize = windowSize / 60;
    maxAlertsPerWindow = 10; // 10 alerts per minute is fatiguing
  } else if (timeUnit.toLowerCase() === "days") {
    windowSize = windowSize * 24;
    maxAlertsPerWindow = 100; // 100 alerts per day is fatiguing
  }

  // Sort alerts by timestamp
  const sortedAlerts = [...alerts].sort(
    (a, b) => a.lastReceived.getTime() - b.lastReceived.getTime()
  );

  const results = [];
  let windowStart = sortedAlerts[0].lastReceived.getTime();
  let count = 0;

  sortedAlerts.forEach((alert) => {
    if (alert.lastReceived.getTime() - windowStart < windowSize) {
      // Alert is within the current window
      count += 1;
    } else {
      // Alert is outside the current window, move the window
      while (alert.lastReceived.getTime() - windowStart >= windowSize) {
        // Push the current count to the results and reset the count
        results.push({
          time: new Date(windowStart),
          count: count,
          fatigueScore:
            count === 1
              ? 0
              : Math.floor(
                  Math.min(Math.max((count / maxAlertsPerWindow) * 100, 1), 100)
                ),
        });
        windowStart += windowSize; // Move window forward by windowSize
        count = 0;
      }
      count += 1; // Count the current alert in the new window
    }
  });

  // Push the last window's count
  if (count > 0) {
    results.push({
      time: new Date(windowStart),
      count: count,
      fatigueScore:
        count === 1
          ? 0
          : Math.floor(
              Math.min(Math.max((count / maxAlertsPerWindow) * 100, 1), 100)
            ),
    });
  }

  return results;
};
