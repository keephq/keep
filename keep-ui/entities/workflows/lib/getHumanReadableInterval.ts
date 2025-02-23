import { formatDuration, intervalToDuration } from "date-fns";

export function getHumanReadableInterval(interval: number | string) {
  try {
    const duration = intervalToDuration({
      start: 0,
      end: Number(interval) * 1000, // convert seconds to milliseconds
    });
    const formattedInterval = formatDuration(duration, {
      format: ["days", "hours", "minutes", "seconds"],
      zero: false,
      delimiter: " ",
    });
    return formattedInterval;
  } catch (error) {
    console.error("Error formatting interval", error);
    return "Invalid interval";
  }
}
