import React, { useEffect, useState } from "react";
import { Title } from "@tremor/react";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/20/solid";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { usePathname } from "next/navigation";
import Skeleton from "react-loading-skeleton";
import { FacetValue } from "./facet-value";
import { FacetOptionDto } from "./models";
import { TrashIcon } from "@heroicons/react/24/outline";

export interface FacetProps {
  name: string;
  isStatic: boolean;
  options: FacetOptionDto[];
  showSkeleton: boolean;
  showIcon?: boolean;
  facetKey: string;
  facetState: any;
  onSelectOneOption: (value: string) => void;
  onSelectAllOptions: () => void;
  onSelect: (value: string) => void;
  onLoadOptions: () => void;
  onDelete: () => void;
}

export const Facet: React.FC<FacetProps> = ({
  name,
  isStatic,
  options,
  facetKey,
  showIcon = true,
  showSkeleton,
  facetState,
  onSelect,
  onSelectOneOption: selectOneOption,
  onSelectAllOptions: selectAllOptions,
  onLoadOptions,
  onDelete
}) => {
  const pathname = usePathname();
  // Get preset name from URL
  const presetName = pathname?.split("/").pop() || "default";

  // Store open/close state in localStorage with a unique key per preset and facet
  const [isOpen, setIsOpen] = useState<boolean>(!!options?.length);
  const [isLoaded, setIsLoaded] = useState<boolean>(!!options?.length);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    setIsOpen(!!options); // Sync prop change with state
    setIsLoaded(!!options); // Sync prop change with state

    if (isLoading && options) {
      setIsLoading(false)
    }
  // disabling as the effect has to only run on options change"
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options]);

  // Store filter value in localStorage per preset and facet
  const [filter, setFilter] = useLocalStorage<string>(
    `facet-${presetName}-${facetKey}-filter`,
    ""
  );

  const handleExpandCollapse = (isOpen: boolean) => {
    setIsOpen(!isOpen)

    if (!isLoaded && !isLoading) {
      onLoadOptions();
      setIsLoading(true)
    }
  }

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
        className="relative lex items-center justify-between px-2 py-2 cursor-pointer hover:bg-gray-50"
        onClick={() => handleExpandCollapse(isOpen)}
      >
        <div className="flex items-center space-x-2">
          <Icon className="size-5 -m-0.5 text-gray-600" />
          <Title className="text-sm">{name}</Title>
        </div>
        {
            !isStatic && (
              <button
                onClick={(mouseEvent) => {
                  mouseEvent.preventDefault();
                  mouseEvent.stopPropagation();
                  onDelete();
                }}
                className="absolute right-2 top-2 p-1 text-gray-400 hover:text-gray-600"
              >
                <TrashIcon className="h-4 w-4" />
              </button>
            )
          }
      </div>

      {isOpen && (
        <div>
          {options.length >= 10 && (
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
            ) : options?.length > 0 ? (
              options.map((facetOption, index) => (
                <FacetValue
                  key={facetOption.display_name + index}
                  label={facetOption.display_name}
                  count={facetOption.matches_count}
                  isExclusivelySelected={checkIfOptionExclusievlySelected(facetOption.display_name)}
                  isSelected={facetState?.[facetOption.display_name] !== false}
                  onToggleOption={() => onSelect(facetOption.display_name)}
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
