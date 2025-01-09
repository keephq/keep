import React from "react";
import { Title } from "@tremor/react";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/20/solid";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { usePathname } from "next/navigation";
import Skeleton from "react-loading-skeleton";
import { FacetValue } from "./facet-value";
import { FacetOptionDto } from "./models";

export interface FacetProps {
  name: string;
  options: FacetOptionDto[];
  showSkeleton: boolean;
  showIcon?: boolean;
  facetKey: string;
  facetState: any;
  onSelectOneOption: (value: string) => void;
  onSelectAllOptions: () => void;
  onSelect: (value: string) => void;
}

export const Facet: React.FC<FacetProps> = ({
  name,
  options: values,
  facetKey,
  showIcon = true,
  showSkeleton,
  facetState,
  onSelect: select,
  onSelectOneOption: selectOneOption,
  onSelectAllOptions: selectAllOptions,
}) => {
  const pathname = usePathname();
  // Get preset name from URL
  const presetName = pathname?.split("/").pop() || "default";

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
    v.value.toLowerCase().includes(filter.toLowerCase())
  );

  function checkIfOptionExclusievlySelected(optionValue: string): boolean {
    if (!facetState) {
        return false;
    }

    const isSelected = facetState?.[optionValue];
    const restNotSelected = Object.entries(facetState).filter(([key, value]) => key !== optionValue).every(([key, value]) => !value);

    return isSelected && restNotSelected;
  }

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
            {showSkeleton ? (
              Array.from({ length: 3 }).map((_, index) => (
                <div
                  key={`skeleton-${index}`}
                  className="flex items-center px-2 py-1 gap-2"
                >
                  <Skeleton containerClassName="h-4 w-4" />
                  <Skeleton containerClassName="h-4 flex-1" />
                </div>
              ))
            ) : values.length > 0 ? (
              filteredValues.map((facetOption) => (
                <FacetValue
                  key={facetOption.display_name}
                  label={facetOption.display_name}
                  count={facetOption.count}
                  isExclusivelySelected={checkIfOptionExclusievlySelected(facetOption.display_name)}
                  isSelected={facetState?.[facetOption.display_name] !== false}
                  onToggleOption={() => select(facetOption.display_name)}
                  onSelectOneOption={(value: string) => selectOneOption(value)}
                  onSelectAllOptions={() => selectAllOptions()}
                  facetKey={facetKey}
                  showIcon={showIcon}
                  //   facetFilters={facetFilters}
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
