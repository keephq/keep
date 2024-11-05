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
      // When clicking "All", reset to include all values (empty included array)
      onSelect("", false, true);
    } else {
      // When clicking "Only", set to only include this value
      onSelect(label, true, true);
    }
  };

  // Initialize the filter if it doesn't exist
  const currentFilter = facetFilters[facetKey] || {
    included: [],
    excluded: [],
  };

  // Calculate whether this value is actually selected
  const isValueSelected =
    !currentFilter?.length || currentFilter.includes(label);

  return (
    <div
      className="flex items-center justify-between px-2 py-1 hover:bg-gray-100 rounded-sm cursor-pointer group"
      onClick={handleCheckboxClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={isValueSelected}
          onClick={handleCheckboxClick}
          onChange={() => {}}
          style={{ accentColor: "#eb6221" }} // orange-500 color code
          className="h-4 w-4 rounded border-gray-300 cursor-pointer"
        />
        {showIcon && facetKey === "source" && (
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
        {showIcon && facetKey === "severity" && (
          <AlertSeverity severity={label as Severity} marginLeft={false} />
        )}
        {showIcon && facetKey === "status" && (
          <Icon
            icon={getStatusIcon(label)}
            size="sm"
            color={getStatusColor(label)}
          />
        )}
        {showIcon && facetKey === "assignee" && (
          <Icon icon={UserCircleIcon} size="sm" className="text-gray-600" />
        )}
        <Text>{label}</Text>
      </div>
      <div className="min-w-[32px] flex justify-end">
        {isHovered ? (
          <button
            onClick={handleActionClick}
            className="text-xs text-orange-600 hover:text-orange-800 w-8"
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
    <div className="border-b border-gray-200">
      <div
        className="flex items-center justify-between px-2 py-2 cursor-pointer hover:bg-gray-50"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center space-x-2">
          <Icon
            icon={isOpen ? ChevronDownIcon : ChevronRightIcon}
            size="sm"
            className="text-gray-600"
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
                  isOnlySelected={
                    facetFilters[facetKey]?.length === 1 &&
                    facetFilters[facetKey][0] === value.label
                  }
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
}

const AlertFacets: React.FC<AlertFacetsProps> = ({
  alerts,
  facetFilters,
  onSelect,
}) => {
  const getFacetValues = (key: keyof AlertDto): FacetValue[] => {
    const valueMap = new Map<string, number>();
    let nullCount = 0;

    alerts.forEach((alert) => {
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

    // Add n/a value for facets that support it
    if (shouldShowNAValue(key) && nullCount > 0) {
      values.push({
        label: "n/a",
        count: nullCount,
        isSelected:
          facetFilters[key]?.includes("n/a") || !facetFilters[key]?.length,
      });
    }

    // Apply special sorting for severity facet
    if (key === "severity") {
      values.sort((a, b) => {
        if (a.label === "n/a") return 1; // Always put n/a last
        if (b.label === "n/a") return -1;
        const orderDiff = getSeverityOrder(a.label) - getSeverityOrder(b.label);
        if (orderDiff !== 0) return orderDiff;
        return b.count - a.count;
      });
    } else {
      // Other facets: sort by count but always keep n/a last
      values.sort((a, b) => {
        if (a.label === "n/a") return 1;
        if (b.label === "n/a") return -1;
        return b.count - a.count;
      });
    }

    return values;
  };

  // Helper function to determine which facets should show n/a values
  const shouldShowNAValue = (key: keyof AlertDto): boolean => {
    // Add facet keys that should show n/a values
    return ["assignee"].includes(key as string);
  };

  // Modify FacetValue component to handle n/a value display
  const getIconForValue = (facetKey: string, label: string) => {
    if (label === "n/a") {
      return XCircleIcon;
    }

    if (facetKey === "source") {
      return null; // Will use Image component instead
    }

    if (facetKey === "severity") {
      return null; // Will use AlertSeverity component
    }

    if (facetKey === "status") {
      return getStatusIcon(label);
    }

    if (facetKey === "assignee") {
      return UserCircleIcon;
    }

    return null;
  };

  return (
    <div className="h-full">
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
      </div>
    </div>
  );
};

export default AlertFacets;
