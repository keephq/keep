export const getSeverityBorderStyle = (severity?: string) => {
  switch (severity) {
    case "critical":
      return "border-l-4 border-red-500";
    case "high":
    case "error":
      return "border-l-4 border-orange-500";
    case "warning":
      return "border-l-4 border-yellow-500";
    case "info":
      return "border-l-4 border-indigo-500";
    default:
      return "border-l-4 border-emerald-500";
  }
};
