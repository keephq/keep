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
  optionsLoading: boolean;
  optionsReloading: boolean;
  showIcon?: boolean;
  facetKey: string;
  facetState: Set<string>;
  renderOptionLabel?: (optionDisplayName: string) => JSX.Element | string | undefined;
  renderIcon?: (option_display_name: string) => JSX.Element | undefined;
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
  optionsLoading,
  optionsReloading,
  facetState,
  onSelect,
  onSelectOneOption: selectOneOption,
  onSelectAllOptions: selectAllOptions,
  onLoadOptions,
  onDelete,
  renderIcon,
  renderOptionLabel
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
      setIsLoading(false);
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
    setIsOpen(!isOpen);

    if (!isLoaded && !isLoading) {
      onLoadOptions();
      setIsLoading(true);
    }
  };

  function checkIfOptionExclusievlySelected(optionValue: string): boolean {
    if (!facetState) {
      return false;
    }

    const isSelected = !facetState.has(optionValue);
    const restNotSelected = options
      .filter((option) => option.display_name !== optionValue)
      .every((option) => facetState.has(option.display_name));

    return isSelected && restNotSelected;
  }

  const Icon = isOpen ? ChevronDownIcon : ChevronRightIcon;

  function renderSkeleton(key: string) {
    return (
      <div className="flex h-7 items-center px-2 py-1 gap-2" key={key}>
        <Skeleton containerClassName="h-4 w-4" />
        <Skeleton containerClassName="h-4 flex-1" />
      </div>
    );
  }

  function renderFacetValue(facetOption: FacetOptionDto, index: number) {
    return (
      <FacetValue
        key={facetOption.display_name + index}
        label={facetOption.display_name}
        count={facetOption.matches_count}
        showIcon={showIcon}
        isExclusivelySelected={checkIfOptionExclusievlySelected(
          facetOption.display_name
        )}
        isSelected={
          !facetState.has(facetOption.display_name) &&
          facetOption.matches_count > 0
        }
        renderLabel={() => renderOptionLabel && renderOptionLabel(facetOption.display_name)}
        renderIcon={() => renderIcon && renderIcon(facetOption.display_name)}
        onToggleOption={() => onSelect(facetOption.display_name)}
        onSelectOneOption={(value: string) => selectOneOption(value)}
        onSelectAllOptions={() => selectAllOptions()}
      />
    );
  }

  function renderBody() {
    if (optionsLoading) {
      return Array.from({ length: 3 }).map((_, index) =>
        renderSkeleton(`skeleton-${index}`)
      );
    }

    const filteredOptions = options.filter((facetOption) =>
      facetOption.display_name
        .toLocaleLowerCase()
        .includes(filter.toLocaleLowerCase())
    );

    if (!filteredOptions.length) {
      return (
        <div className="px-2 py-1 text-sm text-gray-500 italic">
          No matching values found
        </div>
      );
    }

    return filteredOptions.map((facetOption, index) =>
      renderFacetValue(facetOption, index)
    );
  }

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
        {!isStatic && (
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
        )}
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
          <div className={`max-h-60 overflow-y-auto${optionsReloading ? ' pointer-events-none opacity-70' : ''}`}>{renderBody() as any}</div>
        </div>
      )}
    </div>
  );
};
