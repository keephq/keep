import React, { useCallback, useMemo } from "react";
import { Icon } from "@tremor/react";
import Image from "next/image";
import { Text } from "@tremor/react";
import { FacetValueProps } from "./alert-table-facet-types";
import { getStatusIcon, getStatusColor } from "@/shared/lib/status-utils";
import { BellIcon, BellSlashIcon, FireIcon } from "@heroicons/react/24/outline";
import { Severity } from "./models";
import { AlertSeverityBorderIcon } from "./alert-severity-border";
import clsx from "clsx";
import { useIncidents } from "@/utils/hooks/useIncidents";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import { UserStatefulAvatar } from "@/entities/users/ui";
import { useUser } from "@/entities/users/model/useUser";

const AssigneeLabel = ({ email }: { email: string }) => {
  const user = useUser(email);
  return user ? user.name : email;
};

export const FacetValue: React.FC<FacetValueProps> = ({
  label,
  count,
  isSelected,
  onSelect,
  facetKey,
  showIcon = false,
  facetFilters,
}) => {
  const { data: incidents } = useIncidents(
    true,
    100,
    undefined,
    undefined,
    undefined,
    {
      revalidateOnFocus: false,
    }
  );

  const incidentMap = useMemo(() => {
    return new Map(
      incidents?.items.map((incident) => [
        incident.id.replaceAll("-", ""),
        incident,
      ]) || []
    );
  }, [incidents]);

  const incident = useMemo(
    () => (facetKey === "incident" ? incidentMap.get(label) : null),
    [incidentMap, facetKey, label]
  );

  if (facetKey === "incident") {
    console.log(label, incident, incidentMap, incidents?.items);
  }

  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSelect(label, false, false);
  };

  const isExclusivelySelected = () => {
    const currentFilter = facetFilters[facetKey] || [];
    return currentFilter.length === 1 && currentFilter[0] === label;
  };

  const handleActionClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isExclusivelySelected()) {
      onSelect("", false, true);
    } else {
      onSelect(label, true, true);
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
        return <AlertSeverityBorderIcon severity={label as Severity} />;
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
      if (facetKey === "incident") {
        if (incident) {
          return (
            <Icon
              icon={getStatusIcon(incident.status)}
              size="sm"
              color={getStatusColor(incident.status)}
              className="!p-0"
            />
          );
        }
        return (
          <Icon icon={FireIcon} size="sm" className="text-gray-600 !p-0" />
        );
      }
      return null;
    },
    [incident]
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
        if (incident) {
          return getIncidentName(incident);
        } else {
          return label;
        }
      }
      return <span className="capitalize">{label}</span>;
    },
    [incident]
  );

  const currentFilter = facetFilters[facetKey] || [];
  const isValueSelected =
    !currentFilter?.length || currentFilter.includes(label);

  return (
    <div
      className="flex items-center px-2 py-1 hover:bg-gray-100 rounded-sm cursor-pointer group"
      onClick={handleCheckboxClick}
    >
      <div className="flex items-center min-w-[24px]">
        <input
          type="checkbox"
          checked={isValueSelected}
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
        <Text className="truncate">{humanizeLabel(label, facetKey)}</Text>
      </div>

      <div className="flex-shrink-0 w-8 text-right flex justify-end">
        <button
          onClick={handleActionClick}
          className="text-xs text-orange-600 hover:text-orange-800 hidden group-hover:block"
        >
          {isExclusivelySelected() ? "All" : "Only"}
        </button>
        {count > 0 && (
          <Text className="text-xs text-gray-500 group-hover:hidden">
            {count}
          </Text>
        )}
      </div>
    </div>
  );
};
