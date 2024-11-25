import clsx from "clsx";
import { Severity } from "./models";

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

const getSeverityLabelClassName = (severity?: Severity) => {
  switch (severity) {
    case "critical":
      return "bg-red-100";
    case "high":
    case "error":
      return "bg-orange-100";
    case "warning":
      return "bg-yellow-100";
    case "info":
      return "bg-blue-100";
    default:
      return "bg-emerald-100";
  }
};

const getSeverityTextClassName = (severity?: Severity) => {
  switch (severity) {
    case "critical":
      return "text-red-500";
    case "high":
    case "error":
      return "text-orange-500";
    case "warning":
      return "text-amber-900";
    case "info":
      return "text-blue-500";
    default:
      return "text-emerald-500";
  }
};

export function AlertSeverityBorder({
  severity,
}: {
  severity: Severity | undefined;
}) {
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

export function AlertSeverityBorderIcon({ severity }: { severity: Severity }) {
  return (
    <div
      className={clsx("w-1 h-4 rounded-lg", getSeverityBgClassName(severity))}
    />
  );
}

export function AlertSeverityLabel({ severity }: { severity: Severity }) {
  return (
    <span
      className={clsx(
        "flex items-center gap-1 text-sm font-medium py-0.5 px-2 overflow-hidden relative",
        getSeverityLabelClassName(severity)
      )}
    >
      <div
        className={clsx("w-1 h-4 rounded-lg", getSeverityBgClassName(severity))}
      />
      <span className={clsx("capitalize", getSeverityTextClassName(severity))}>
        {severity}
      </span>
    </span>
  );
}
