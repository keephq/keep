import React, { useCallback, useMemo } from "react";
import { Icon } from "@tremor/react";
import Image from "next/image";
import { Text } from "@tremor/react";
import { getStatusIcon, getStatusColor } from "@/shared/lib/status-utils";
import { BellIcon, BellSlashIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";
import { UserStatefulAvatar } from "@/entities/users/ui";
import { useUser } from "@/entities/users/model/useUser";
import { SeverityBorderIcon, UISeverity } from "@/shared/ui";

const AssigneeLabel = ({ email }: { email: string }) => {
  const user = useUser(email);
  return user ? user.name : email;
};

export interface FacetValueProps {
  label: string;
  count: number;
  isExclusivelySelected: boolean;
  isSelected: boolean;
  facetKey: string;
  showIcon: boolean;
  onSelectOneOption: (value: string) => void;
  onSelectAllOptions: () => void;
  onToggleOption: (value: string) => void;
}

export const FacetValue: React.FC<FacetValueProps> = ({
  label,
  count,
  isSelected,
  isExclusivelySelected,
  facetKey,
  showIcon = false,
    onSelectOneOption,
    onSelectAllOptions,
    onToggleOption: onSelect
}) => {
  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSelect(label);
  };

  const handleActionClick = (e: React.MouseEvent) => {
    e.stopPropagation();

    if (isExclusivelySelected) {
      onSelectAllOptions();

    } else {
      onSelectOneOption(label)
    }
  };

  const getValueIcon = useCallback(
    (label: string, facetKey: string) => {
      if (facetKey === "source") {
        return (
          <Image
            className="inline-block"
            alt={label}
            height={16}
            width={16}
            title={label}
            src={
              label.includes("@")
                ? "/icons/mailgun-icon.png"
                : `/icons/${label}-icon.png`
            }
          />
        );
      }
      if (facetKey === "severity") {
        return <SeverityBorderIcon severity={label as UISeverity} />;
      }
      if (facetKey === "assignee") {
        return <UserStatefulAvatar email={label} size="xs" />;
      }
      if (facetKey === "status") {
        return (
          <Icon
            icon={getStatusIcon(label)}
            size="sm"
            color={getStatusColor(label)}
            className="!p-0"
          />
        );
      }
      if (facetKey === "dismissed") {
        return (
          <Icon
            icon={label === "true" ? BellSlashIcon : BellIcon}
            size="sm"
            className="text-gray-600 !p-0"
          />
        );
      }
      // if (facetKey === "incident") {
      //   if (incident) {
      //     return (
      //       <Icon
      //         icon={getStatusIcon(incident.status)}
      //         size="sm"
      //         color={getStatusColor(incident.status)}
      //         className="!p-0"
      //       />
      //     );
      //   }
      //   return (
      //     <Icon icon={FireIcon} size="sm" className="text-gray-600 !p-0" />
      //   );
      // }
      return null;
    },
    []
  );

  const humanizeLabel = useCallback(
    (label: string, facetKey: string) => {
      if (facetKey === "assignee") {
        if (label === "n/a") {
          return "Not assigned";
        }
        return <AssigneeLabel email={label} />;
      }
      if (facetKey === "incident") {
        if (label === "n/a") {
          return "No incident";
        }
        // if (incident) {
        //   return getIncidentName(incident);
        // } else {
          return label;
        // }
      }
      if (facetKey === "dismissed") {
        return label === "true" ? "Dismissed" : "Not dismissed";
      }
      return <span className="capitalize">{label}</span>;
    },
    []
  );

  return (
    <div
      className={`flex items-center px-2 py-1 hover:bg-gray-100 rounded-sm cursor-pointer group ${ !count ? "opacity-50 pointer-events-none" : "" }`}
      onClick={handleCheckboxClick}
    >
      <div className="flex items-center min-w-[24px]">
        <input
          type="checkbox"
          checked={isSelected && count > 0}
          onClick={handleCheckboxClick}
          onChange={() => {}}
          style={{ accentColor: "#eb6221" }}
          className="h-4 w-4 rounded border-gray-300 cursor-pointer"
        />
      </div>

      <div className="flex-1 flex items-center min-w-0 gap-1" title={label}>
        {showIcon && (
          <div className={clsx("flex items-center")}>
            {getValueIcon(label, facetKey)}
          </div>
        )}
        <Text className="truncate" title={label}>{humanizeLabel(label, facetKey)}</Text>
      </div>

      <div className="flex-shrink-0 w-8 text-right flex justify-end">
        <button
          onClick={handleActionClick}
          className="text-xs text-orange-600 hover:text-orange-800 hidden group-hover:block"
        >
          {isExclusivelySelected ? "All" : "Only"}
        </button>
        {(
          <Text className="text-xs text-gray-500 group-hover:hidden">
            {count}
          </Text>
        )}
      </div>
    </div>
  );
};
