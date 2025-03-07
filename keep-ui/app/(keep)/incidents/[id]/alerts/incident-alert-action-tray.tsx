import { AlertDto } from "@/entities/alerts/model";
import { EyeIcon, LinkIcon } from "@heroicons/react/24/outline";
import { Icon } from "@tremor/react";

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
  return (
    <div className="flex items-center h-full border-l border-gray-200 bg-white pl-2">
      <div className="flex items-center gap-1 transition-all duration-200 transform translate-x-2 opacity-0 group-hover/row:translate-x-0 group-hover/row:opacity-100">
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
