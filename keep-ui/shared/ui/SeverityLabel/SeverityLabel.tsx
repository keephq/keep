import clsx from "clsx";
import {
  UISeverity,
  getSeverityBgClassName,
  getSeverityLabelClassName,
  getSeverityTextClassName,
} from "../utils/severity-utils";

export function SeverityLabel({ severity }: { severity: UISeverity }) {
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
