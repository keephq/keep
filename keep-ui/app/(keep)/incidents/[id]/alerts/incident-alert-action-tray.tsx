import { AlertDto } from "@/entities/alerts/model";
import { EyeIcon, LinkIcon } from "@heroicons/react/24/outline";
import { Icon } from "@tremor/react";
import { IoExpandSharp } from "react-icons/io5";
import { clsx } from "clsx";
import { Button } from "@/components/ui";
import { useAlertRowStyle } from "@/entities/alerts/model/useAlertRowStyle";
import { useExpandedRows } from "@/utils/hooks/useExpandedRows";

interface Props {
  alert: AlertDto;
  onViewAlert: (alert: AlertDto) => void;
  onUnlink: (alert: AlertDto) => void;
  isCandidate: boolean;
}

export function IncidentAlertActionTray({
  alert,
  onViewAlert,
  onUnlink,
  isCandidate,
}: Props) {
  const [rowStyle] = useAlertRowStyle();
  const { isRowExpanded, toggleRowExpanded } =
    useExpandedRows("incident-alerts");
  const expanded = isRowExpanded(alert.fingerprint);

  const actionIconButtonClassName = clsx(
    "text-gray-500 leading-none p-2 prevent-row-click hover:bg-slate-200 [&>[role='tooltip']]:z-50",
    rowStyle === "relaxed" ? "rounded-tremor-default" : "rounded-none"
  );

  return (
    <div className="flex items-center justify-end relative group">
      <div
        className={clsx("flex items-center", [
          "transition-opacity duration-100",
          "opacity-0 bg-orange-100",
          "group-hover:opacity-100",
        ])}
      >
        <Button
          className={actionIconButtonClassName}
          onClick={(e) => {
            e.stopPropagation();
            toggleRowExpanded(alert.fingerprint);
          }}
          variant="light"
          icon={() => (
            <Icon
              icon={IoExpandSharp}
              className={clsx(
                "w-4 h-4 object-cover rounded",
                expanded ? "text-orange-400" : "text-gray-500"
              )}
            />
          )}
          tooltip={expanded ? "Collapse Row" : "Expand Row"}
        />
        <button
          onClick={(e) => {
            e.stopPropagation();
            onViewAlert(alert);
          }}
          className="p-1.5 hover:bg-gray-100 rounded-md transition-colors"
          title="View Alert Details"
        >
          <Icon icon={EyeIcon} size="sm" className="text-gray-500" />
        </button>
        {!isCandidate && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onUnlink(alert);
            }}
            className="p-1.5 hover:bg-gray-100 rounded-md transition-colors"
            title="Unlink from incident"
          >
            <Icon
              icon={LinkIcon}
              size="sm"
              className="rotate-45 text-gray-500"
            />
          </button>
        )}
      </div>
    </div>
  );
}
