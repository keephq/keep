import React from "react";
import { AlertDto } from "@/entities/alerts/model";
import { clsx } from "clsx";
import { useAlertRowStyle } from "@/entities/alerts/model/useAlertRowStyle";
interface Props {
  alert: AlertDto;
  className?: string;
}

export function AlertName({ alert, className }: Props) {
  const [rowStyle] = useAlertRowStyle();
  const isCompact = rowStyle === "default";

  return (
    <div
      className={`flex items-center justify-between w-full ${className || ""}`}
    >
      <div
        className={clsx(
          isCompact
            ? "truncate whitespace-nowrap"
            : "line-clamp-3 whitespace-pre-wrap",
          "flex-grow"
        )}
        title={alert.name}
      >
        {alert.name}
      </div>
    </div>
  );
}
