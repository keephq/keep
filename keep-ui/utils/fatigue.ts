import { AlertDto } from "app/alerts/models";

const WINDOW_SIZE = 60 * 60 * 1000; // 60 minutes in milliseconds
export const MAX_ALERTS_PER_WINDOW = 20; // This number might come from historical data or whatever we decide

export const calculateFatigue = (alerts: AlertDto[]): any[] => {
  // Sort alerts by timestamp
  const sortedAlerts = alerts.sort(
    (a, b) => a.lastReceived.getTime() - b.lastReceived.getTime()
  );

  const results = [];
  let windowStart = sortedAlerts[0].lastReceived.getTime();
  let count = 0;

  sortedAlerts.forEach((alert) => {
    if (alert.lastReceived.getTime() - windowStart < WINDOW_SIZE) {
      // Alert is within the current window
      count += 1;
    } else {
      // Alert is outside the current window, move the window
      while (alert.lastReceived.getTime() - windowStart >= WINDOW_SIZE) {
        // Push the current count to the results and reset the count
        results.push({
          time: new Date(windowStart),
          count: count,
          fatigueScore: Math.min(
            Math.max((count / MAX_ALERTS_PER_WINDOW) * 100, 1),
            100
          ),
        });
        windowStart += WINDOW_SIZE; // Move window forward by 5 minutes
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
      fatigueScore: Math.min(
        Math.max((count / MAX_ALERTS_PER_WINDOW) * 100, 1),
        100
      ),
    });
  }

  return results;
};
