import clsx from "clsx";
import { UISeverity, getSeverityBgClassName } from "../utils/severity-utils";

export function SeverityBorderIcon({ severity }: { severity: UISeverity }) {
  return (
    <div
      className={clsx("w-1 h-4 rounded-lg", getSeverityBgClassName(severity))}
    />
  );
}
