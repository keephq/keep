// severity is used for alerts and incidents
export enum UISeverity {
  Critical = "critical",
  High = "high",
  Warning = "warning",
  Low = "low",
  Info = "info",
  Error = "error",
}

export const getSeverityBgClassName = (severity?: UISeverity) => {
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

export const getSeverityLabelClassName = (severity?: UISeverity) => {
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

export const getSeverityTextClassName = (severity?: UISeverity) => {
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
