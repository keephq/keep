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
        expanded ? "w-full max-w-md" : "w-full",
        className
      )}
    >
      <div
        className={clsx(
          expanded
            ? "whitespace-pre-wrap break-words max-w-md"
            : isCompact
            ? "truncate whitespace-nowrap"
            : "line-clamp-3 whitespace-pre-wrap",
          "flex-grow"
        )}
        title={expanded ? undefined : alert.name}
      >
        {alert.name}
      </div>
    </div>
  );
}
