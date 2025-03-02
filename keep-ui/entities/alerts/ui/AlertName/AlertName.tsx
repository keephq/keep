import React from "react";
import { AlertDto } from "@/entities/alerts/model";
import { clsx } from "clsx";
import { useLocalStorage } from "utils/hooks/useLocalStorage";

interface Props {
  alert: AlertDto;
  className?: string;
}

export function AlertName({ alert, className }: Props) {
  const [rowStyle] = useLocalStorage("alert-table-row-style", "default");
  const isDense = rowStyle === "dense";

  return (
    <div
      className={`flex items-center justify-between w-full ${className || ""}`}
    >
      <div
        className={clsx(
          isDense
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
