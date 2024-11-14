import React, { useCallback, useEffect } from "react";
import {
  AlertFacetsProps,
  FacetValue,
  FacetFilters,
} from "./alert-table-facet-types";
import { Facet } from "./alert-table-facet";
import {
  getFilteredAlertsForFacet,
  getSeverityOrder,
} from "./alert-table-facet-utils";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { AlertDto } from "./models";
import {
  DynamicFacetWrapper,
  AddFacetModal,
} from "./alert-table-facet-dynamic";
import { PlusIcon } from "@heroicons/react/24/outline";

export const AlertFacets: React.FC<AlertFacetsProps> = ({
  alerts,
  facetFilters,
  setFacetFilters,
  dynamicFacets,
  setDynamicFacets,
  onDelete,
  className,
  table,
}) => {
  const timeRangeFilter = table
    .getState()
    .columnFilters.find((filter) => filter.id === "lastReceived");

  const timeRange = timeRangeFilter?.value as
    | { start: Date; end: Date; isFromCalendar: boolean }
    | undefined;

  const presetName = window.location.pathname.split("/").pop() || "default";

  const [isModalOpen, setIsModalOpen] = useLocalStorage<boolean>(
    `addFacetModalOpen-${presetName}`,
    false
  );

  const handleSelect = (
    facetKey: string,
    value: string,
    exclusive: boolean,
    isAllOnly: boolean
  ) => {
    const newFilters = { ...facetFilters };

    if (isAllOnly) {
      if (exclusive) {
        newFilters[facetKey] = [value];
      } else {
        delete newFilters[facetKey];
      }
    } else {
      if (exclusive) {
        newFilters[facetKey] = [value];
      } else {
        const currentValues = newFilters[facetKey] || [];
        if (currentValues.includes(value)) {
          newFilters[facetKey] = currentValues.filter((v) => v !== value);
          if (newFilters[facetKey].length === 0) {
            delete newFilters[facetKey];
          }
        } else {
          newFilters[facetKey] = [...currentValues, value];
        }
      }
    }

    setFacetFilters(newFilters);
  };

  const getFacetValues = useCallback(
    (key: keyof AlertDto | string): FacetValue[] => {
      const filteredAlerts = getFilteredAlertsForFacet(
        alerts,
        facetFilters,
        key,
        timeRange
      );
      const valueMap = new Map<string, number>();
      let nullCount = 0;

      filteredAlerts.forEach((alert) => {
        let value;

        // Handle nested keys like "labels.host"
        if (typeof key === "string" && key.includes(".")) {
          const [parentKey, childKey] = key.split(".");
          const parentValue = alert[parentKey as keyof AlertDto];

          if (
            typeof parentValue === "object" &&
            parentValue !== null &&
            !Array.isArray(parentValue) &&
            !(parentValue instanceof Date)
          ) {
            value = (parentValue as Record<string, unknown>)[childKey];
          } else {
            value = undefined;
          }
        } else {
          value = alert[key as keyof AlertDto];
        }

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

      if (["assignee", "incident"].includes(key as string) && nullCount > 0) {
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
          const orderDiff =
            getSeverityOrder(a.label) - getSeverityOrder(b.label);
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
    },
    [alerts, facetFilters, timeRange]
  );

  const staticFacets = [
    "severity",
    "status",
    "source",
    "assignee",
    "dismissed",
    "incident",
  ];

  // TODO: move to the alert-table.tsx
  useEffect(
    function setInitialFacetFilters() {
      setFacetFilters((facetFilters) => {
        return Object.keys(facetFilters).reduce((acc, key) => {
          acc[key] =
            facetFilters[key]?.length === 0
              ? getFacetValues(key as keyof AlertDto).map((v) => v.label)
              : facetFilters[key];
          return acc;
        }, {} as FacetFilters);
      });
    },
    [getFacetValues, setFacetFilters]
  );

  const handleAddFacet = (column: string) => {
    setDynamicFacets([
      ...dynamicFacets,
      {
        key: column,
        name: column.charAt(0).toUpperCase() + column.slice(1),
      },
    ]);
  };

  const handleDeleteFacet = (facetKey: string) => {
    setDynamicFacets(dynamicFacets.filter((df) => df.key !== facetKey));
    const newFilters = { ...facetFilters };
    delete newFilters[facetKey];
    setFacetFilters(newFilters);
  };

  return (
    <div className={className}>
      <div className="space-y-2">
        {/* Facet button */}
        <button
          onClick={() => setIsModalOpen(true)}
          className="w-full mt-2 px-2 py-1 text-sm text-gray-600 hover:bg-gray-100 rounded flex items-center gap-2"
        >
          <PlusIcon className="h-4 w-4" />
          Add Facet
        </button>
        <Facet
          name="Severity"
          values={getFacetValues("severity")}
          onSelect={(value, exclusive, isAllOnly) =>
            handleSelect("severity", value, exclusive, isAllOnly)
          }
          facetKey="severity"
          facetFilters={facetFilters}
        />
        <Facet
          name="Status"
          values={getFacetValues("status")}
          onSelect={(value, exclusive, isAllOnly) =>
            handleSelect("status", value, exclusive, isAllOnly)
          }
          facetKey="status"
          facetFilters={facetFilters}
        />
        <Facet
          name="Source"
          values={getFacetValues("source")}
          onSelect={(value, exclusive, isAllOnly) =>
            handleSelect("source", value, exclusive, isAllOnly)
          }
          facetKey="source"
          facetFilters={facetFilters}
        />
        <Facet
          name="Assignee"
          values={getFacetValues("assignee")}
          onSelect={(value, exclusive, isAllOnly) =>
            handleSelect("assignee", value, exclusive, isAllOnly)
          }
          facetKey="assignee"
          facetFilters={facetFilters}
        />
        <Facet
          name="Dismissed"
          values={getFacetValues("dismissed")}
          onSelect={(value, exclusive, isAllOnly) =>
            handleSelect("dismissed", value, exclusive, isAllOnly)
          }
          facetKey="dismissed"
          facetFilters={facetFilters}
        />
        <Facet
          name="Incident Related"
          facetKey="incident"
          values={getFacetValues("incident")}
          onSelect={(value, exclusive, isAllOnly) =>
            handleSelect("incident", value, exclusive, isAllOnly)
          }
          facetFilters={facetFilters}
        />
        {/* Dynamic facets */}
        {dynamicFacets.map((facet) => (
          <DynamicFacetWrapper
            key={facet.key}
            name={facet.name}
            values={getFacetValues(facet.key as keyof AlertDto)}
            onSelect={(value, exclusive, isAllOnly) =>
              handleSelect(facet.key, value, exclusive, isAllOnly)
            }
            facetKey={facet.key}
            facetFilters={facetFilters}
            onDelete={() => handleDeleteFacet(facet.key)}
          />
        ))}

        {/* Facet Modal */}
        <AddFacetModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          table={table}
          onAddFacet={handleAddFacet}
          existingFacets={[
            ...staticFacets,
            ...dynamicFacets.map((df) => df.key),
          ]}
        />
      </div>
    </div>
  );
};
