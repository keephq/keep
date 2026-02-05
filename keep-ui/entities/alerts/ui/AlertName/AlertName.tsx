import React from "react";
import { AlertDto } from "@/entities/alerts/model";
import { clsx } from "clsx";
import { useAlertRowStyle } from "@/entities/alerts/model/useAlertRowStyle";

interface Props {
  alert: AlertDto;
  className?: string;
  expanded?: boolean;
}

export function AlertName({ alert, className, expanded }: Props) {
  const [rowStyle] = useAlertRowStyle();
  const isCompact = rowStyle === "default";

  return (
    <div
      className={clsx(
        "flex items-center justify-between",
        // Strictly constrain the width with a fixed value
        expanded ? "max-w-[180px] overflow-hidden" : "",
        className
      )}
    >
      <div
        className={clsx(
          // Use overflow-hidden to ensure content doesn't expand container
          expanded
            ? "whitespace-pre-wrap break-words overflow-hidden max-w-[180px]"
            : isCompact
            ? "truncate whitespace-nowrap"
            : "line-clamp-3 whitespace-pre-wrap",
          // Remove flex-grow which can cause expansion issues
          expanded ? "" : "flex-grow"
        )}
        title={expanded ? undefined : alert.name}
      >
        {alert.name}
      </div>
    </div>
  );
}
