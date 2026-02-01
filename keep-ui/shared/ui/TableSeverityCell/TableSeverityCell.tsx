import clsx from "clsx";
import { UISeverity, getSeverityBgClassName } from "../utils/severity-utils";

export function TableSeverityCell({
  severity,
}: {
  severity: UISeverity | undefined;
}) {
  return (
    <>
      <div
        className={clsx(
          "absolute w-1 h-full top-0 left-0",
          getSeverityBgClassName(severity)
        )}
        aria-label={severity}
      />
      <div className="pl-1" />
    </>
  );
}
