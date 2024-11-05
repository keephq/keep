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
          onChange={() => {}} // Required to avoid React warning
          className="h-4 w-4 rounded border-gray-300"
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
        <span className="truncate text-sm text-gray-700">{label}</span>
      </div>
      <div className="min-w-[32px] flex justify-end">
        {isHovered ? (
          <button
            onClick={handleActionClick}
            className="text-xs text-blue-600 hover:text-blue-800 w-8"
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

    alerts.forEach((alert) => {
      let value = alert[key];

      if (Array.isArray(value)) {
        value.forEach((v) => {
          valueMap.set(v, (valueMap.get(v) || 0) + 1);
        });
      } else if (value !== undefined && value !== null) {
        const strValue = String(value);
        valueMap.set(strValue, (valueMap.get(strValue) || 0) + 1);
      }
    });

    return Array.from(valueMap.entries())
      .map(([label, count]) => ({
        label,
        count,
        isSelected:
          facetFilters[key]?.includes(label) || !facetFilters[key]?.length,
      }))
      .sort((a, b) => b.count - a.count);
  };

  return (
    <div className="h-full pt-[180px]">
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
