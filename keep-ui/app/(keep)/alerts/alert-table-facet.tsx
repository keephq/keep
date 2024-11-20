import React from "react";
import { Title } from "@tremor/react";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/20/solid";
import { FacetProps } from "./alert-table-facet-types";
import { FacetValue } from "./alert-table-facet-value";
import { useLocalStorage } from "utils/hooks/useLocalStorage";

export const Facet: React.FC<FacetProps> = ({
  name,
  values,
  onSelect,
  facetKey,
  facetFilters,
  showIcon = true,
}) => {
  // Get preset name from URL
  const presetName = window.location.pathname.split("/").pop() || "default";

  // Store open/close state in localStorage with a unique key per preset and facet
  const [isOpen, setIsOpen] = useLocalStorage<boolean>(
    `facet-${presetName}-${facetKey}-open`,
    true
  );

  // Store filter value in localStorage per preset and facet
  const [filter, setFilter] = useLocalStorage<string>(
    `facet-${presetName}-${facetKey}-filter`,
    ""
  );

  const filteredValues = values.filter((v) =>
    v.label.toLowerCase().includes(filter.toLowerCase())
  );

  const Icon = isOpen ? ChevronDownIcon : ChevronRightIcon;

  return (
    <div className="pb-2 border-b border-gray-200">
      <div
        className="flex items-center justify-between px-2 py-2 cursor-pointer hover:bg-gray-50"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center space-x-2">
          <Icon className="size-5 -m-0.5 text-gray-600" />
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
                  showIcon={showIcon}
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
