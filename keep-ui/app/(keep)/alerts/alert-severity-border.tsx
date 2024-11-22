import clsx from "clsx";
import { Severity } from "./models";

export function AlertSeverityBorder({
  severity,
}: {
  severity: Severity | undefined;
}) {
  const getSeverityBgClassName = (severity?: Severity) => {
    switch (severity) {
      case "critical":
        return "bg-red-500";
      case "high":
      case "error":
        return "bg-orange-500";
      case "warning":
        return "bg-yellow-500";
      case "info":
        return "bg-blue-500";
      default:
        return "bg-emerald-500";
    }
  };

  return (
    <div
      className={clsx(
        "absolute w-1 h-full top-0 left-0",
        getSeverityBgClassName(severity)
      )}
      aria-label={severity}
    />
  );
}
