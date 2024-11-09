import React, { useState } from "react";
import { Icon, Title, Text } from "@tremor/react";
import Image from "next/image";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  MagnifyingGlassIcon,
  CircleStackIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationCircleIcon,
  UserCircleIcon,
  BellSlashIcon,
  FireIcon,
} from "@heroicons/react/24/outline";
import { AlertDto, Severity } from "./models";
import AlertSeverity from "./alert-severity";

interface FacetValue {
  label: string;
  count: number;
  isSelected: boolean;
}

export interface FacetFilters {
  [key: string]: string[];
}

const getFilteredAlertsForFacet = (
  alerts: AlertDto[],
  facetFilters: FacetFilters,
  excludeFacet: string
): AlertDto[] => {
  return alerts.filter((alert) => {
    return Object.entries(facetFilters).every(([facetKey, includedValues]) => {
      // Skip the current facet when filtering
      if (facetKey === excludeFacet || includedValues.length === 0) {
        return true;
      }

      const value = alert[facetKey as keyof AlertDto];

      if (facetKey === "source") {
        const sources = value as string[];
        if (includedValues.includes("n/a")) {
          return !sources || sources.length === 0;
        }
        return (
          Array.isArray(sources) &&
          sources.some((source) => includedValues.includes(source))
        );
      }

      if (includedValues.includes("n/a")) {
        return value === null || value === undefined || value === "";
      }

      if (value === null || value === undefined || value === "") {
        return false;
      }

      return includedValues.includes(String(value));
    });
  });
};

interface FacetValueProps {
  label: string;
  count: number;
  isSelected: boolean;
  onSelect: (value: string, exclusive: boolean, isAllOnly: boolean) => void;
  facetKey: string;
  showIcon?: boolean;
  isOnlySelected?: boolean;
  facetFilters: FacetFilters;
}

const getStatusIcon = (status: string) => {
  switch (status.toLowerCase()) {
    case "firing":
      return ExclamationCircleIcon;
    case "resolved":
      return CheckCircleIcon;
    case "acknowledged":
      return CircleStackIcon;
    default:
      return CircleStackIcon;
  }
};

const getStatusColor = (status: string) => {
  switch (status.toLowerCase()) {
    case "firing":
      return "red";
    case "resolved":
      return "green";
    case "acknowledged":
      return "blue";
    default:
      return "gray";
  }
};

const getSeverityOrder = (severity: string): number => {
  switch (severity) {
    case "low":
      return 1;
    case "info":
      return 2;
    case "warning":
      return 3;
    case "error":
    case "high":
      return 4;
    case "critical":
      return 5;
    default:
      return 6; // Unknown severities go last
  }
};

const FacetValue: React.FC<FacetValueProps> = ({
  label,
  count,
  isSelected,
  onSelect,
  facetKey,
  showIcon = false,
  facetFilters,
}) => {
  const [isHovered, setIsHovered] = useState(false);

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

  const currentFilter = facetFilters[facetKey] || [];
  const isValueSelected =
    !currentFilter?.length || currentFilter.includes(label);

  return (
    <div
      className="flex items-center px-2 py-1 hover:bg-gray-100 rounded-sm cursor-pointer group"
      onClick={handleCheckboxClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
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

      {showIcon && (
        <div className="flex items-center min-w-[24px] ml-2">
          {facetKey === "source" && (
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
          )}
          {facetKey === "severity" && (
            <AlertSeverity severity={label as Severity} />
          )}
          {facetKey === "assignee" && (
            <Icon
              icon={UserCircleIcon}
              size="sm"
              className="text-gray-600 !p-0"
            />
          )}
          {facetKey === "status" && (
            <Icon
              icon={getStatusIcon(label)}
              size="sm"
              color={getStatusColor(label)}
              className="!p-0"
            />
          )}
          {facetKey === "dismissed" && (
            <Icon
              icon={BellSlashIcon}
              size="sm"
              className="text-gray-600 !p-0"
            />
          )}
          {facetKey === "incident" && (
            <Icon icon={FireIcon} size="sm" className="text-gray-600 !p-0" />
          )}
        </div>
      )}

      <div className="flex-1 min-w-0 mx-2" title={label}>
        <Text className="capitalize truncate">{label}</Text>
      </div>

      <div className="flex-shrink-0 w-8 text-right">
        {isHovered ? (
          <button
            onClick={handleActionClick}
            className="text-xs text-orange-600 hover:text-orange-800 w-full"
          >
            {isExclusivelySelected() ? "All" : "Only"}
          </button>
        ) : (
          count > 0 && <Text className="text-xs text-gray-500">{count}</Text>
        )}
      </div>
    </div>
  );
};

interface FacetProps {
  name: string;
  values: FacetValue[];
  onSelect: (value: string, exclusive: boolean, isAllOnly: boolean) => void;
  facetKey: string;
  facetFilters: FacetFilters;
}

const Facet: React.FC<FacetProps> = ({
  name,
  values,
  onSelect,
  facetKey,
  facetFilters,
}) => {
  const [isOpen, setIsOpen] = useState(true);
  const [filter, setFilter] = useState("");

  const filteredValues = values.filter((v) =>
    v.label.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="pb-2 border-b border-gray-200">
      <div
        className="flex items-center justify-between px-2 py-2 cursor-pointer hover:bg-gray-50"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center space-x-2">
          <Icon
            icon={isOpen ? ChevronDownIcon : ChevronRightIcon}
            size="sm"
            className="text-gray-600 !p-0"
          />
          <Title className="text-sm">{name}</Title>
        </div>
      </div>

      {isOpen && (
        <div>
          {values.length >= 10 && (
            <div className="px-2 mb-1">
              <input
                type="text"
                placeholder="Filter values..."
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
              />
            </div>
          )}
          <div className="max-h-60 overflow-y-auto">
            {values.length > 0 ? (
              filteredValues.map((value) => (
                <FacetValue
                  key={value.label}
                  label={value.label}
                  count={value.count}
                  isSelected={facetFilters[facetKey]?.includes(value.label)}
                  onSelect={onSelect}
                  facetKey={facetKey}
                  showIcon={true}
                  facetFilters={facetFilters}
                />
              ))
            ) : (
              <div className="px-2 py-1 text-sm text-gray-500 italic">
                No matching values found
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

interface AlertFacetsProps {
  alerts: AlertDto[];
  facetFilters: FacetFilters;
  onSelect: (
    facetKey: string,
    value: string,
    exclusive: boolean,
    isAllOnly: boolean
  ) => void;
  className?: string;
}

const AlertFacets: React.FC<AlertFacetsProps> = ({
  alerts,
  facetFilters,
  onSelect,
  className,
}) => {
  const getFacetValues = (key: keyof AlertDto): FacetValue[] => {
    // Get alerts filtered by all other facets except the current one
    const filteredAlerts = getFilteredAlertsForFacet(
      alerts,
      facetFilters,
      key as string
    );

    const valueMap = new Map<string, number>();
    let nullCount = 0;

    filteredAlerts.forEach((alert) => {
      let value = alert[key];

      if (Array.isArray(value)) {
        if (value.length === 0) {
          nullCount++;
        } else {
          value.forEach((v) => {
            valueMap.set(v, (valueMap.get(v) || 0) + 1);
          });
        }
      } else if (value !== undefined && value !== null) {
        const strValue = String(value);
        valueMap.set(strValue, (valueMap.get(strValue) || 0) + 1);
      } else {
        nullCount++;
      }
    });

    let values = Array.from(valueMap.entries()).map(([label, count]) => ({
      label,
      count,
      isSelected:
        facetFilters[key]?.includes(label) || !facetFilters[key]?.length,
    }));

    if (shouldShowNAValue(key) && nullCount > 0) {
      values.push({
        label: "n/a",
        count: nullCount,
        isSelected:
          facetFilters[key]?.includes("n/a") || !facetFilters[key]?.length,
      });
    }

    if (key === "severity") {
      values.sort((a, b) => {
        if (a.label === "n/a") return 1;
        if (b.label === "n/a") return -1;
        const orderDiff = getSeverityOrder(a.label) - getSeverityOrder(b.label);
        if (orderDiff !== 0) return orderDiff;
        return b.count - a.count;
      });
    } else {
      values.sort((a, b) => {
        if (a.label === "n/a") return 1;
        if (b.label === "n/a") return -1;
        return b.count - a.count;
      });
    }

    return values;
  };

  const shouldShowNAValue = (key: keyof AlertDto): boolean => {
    return ["assignee"].includes(key as string);
  };

  return (
    <div className={className}>
      <div className="space-y-2">
        <Facet
          facetKey="severity"
          name="Severity"
          values={getFacetValues("severity")}
          onSelect={(value, exclusive, isAllOnly) =>
            onSelect("severity", value, exclusive, isAllOnly)
          }
          facetFilters={facetFilters}
        />
        <Facet
          facetKey="status"
          name="Status"
          values={getFacetValues("status")}
          onSelect={(value, exclusive, isAllOnly) =>
            onSelect("status", value, exclusive, isAllOnly)
          }
          facetFilters={facetFilters}
        />
        <Facet
          facetKey="source"
          name="Source"
          values={getFacetValues("source")}
          onSelect={(value, exclusive, isAllOnly) =>
            onSelect("source", value, exclusive, isAllOnly)
          }
          facetFilters={facetFilters}
        />
        <Facet
          facetKey="assignee"
          name="Assignee"
          values={getFacetValues("assignee")}
          onSelect={(value, exclusive, isAllOnly) =>
            onSelect("assignee", value, exclusive, isAllOnly)
          }
          facetFilters={facetFilters}
        />
        <Facet
          facetKey="dismissed"
          name="Dismissed"
          values={getFacetValues("dismissed")}
          onSelect={(value, exclusive, isAllOnly) =>
            onSelect("dismissed", value, exclusive, isAllOnly)
          }
          facetFilters={facetFilters}
        />
        <Facet
          facetKey="incident"
          name="Incident Related"
          values={getFacetValues("incident")}
          onSelect={(value, exclusive, isAllOnly) =>
            onSelect("incident", value, exclusive, isAllOnly)
          }
          facetFilters={facetFilters}
        />
      </div>
    </div>
  );
};

export default AlertFacets;
