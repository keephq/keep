import { useEffect, useMemo, useRef, useState } from "react";
import { Title } from "@tremor/react";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/20/solid";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { usePathname } from "next/navigation";
import Skeleton from "react-loading-skeleton";
import { FacetValue } from "./facet-value";
import { FacetDto, FacetOptionDto } from "./models";
import { TrashIcon } from "@heroicons/react/24/outline";
import { useExistingFacetsPanelStore } from "./store";
import { stringToValue, valueToString } from "./store/utils";

export interface FacetProps {
  facet: FacetDto;
  isOpenByDefault?: boolean;
  options?: FacetOptionDto[];
  showIcon?: boolean;
  onLoadOptions?: () => void;
  onDelete?: () => void;
}

export const Facet: React.FC<FacetProps> = ({
  facet,
  options,
  showIcon = true,
  onLoadOptions,
  onDelete,
}) => {
  const pathname = usePathname();
  // Get preset name from URL
  const presetName = pathname?.split("/").pop() || "default";

  // Store open/close state in localStorage with a unique key per preset and facet
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const [isLoaded, setIsLoaded] = useState<boolean>(!!options?.length);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const optionsRef = useRef(options);
  optionsRef.current = options;
  const facetRef = useRef(facet);
  facetRef.current = facet;

  const facetOptionsLoadingState = useExistingFacetsPanelStore(
    (state) => state.facetOptionsLoadingState
  );
  const toggleFacetOption = useExistingFacetsPanelStore(
    (state) => state.toggleFacetOption
  );
  const selectOneFacetOption = useExistingFacetsPanelStore(
    (state) => state.selectOneFacetOption
  );
  const selectAllFacetOptions = useExistingFacetsPanelStore(
    (state) => state.selectAllFacetOptions
  );
  const facetsState = useExistingFacetsPanelStore((state) => state.facetsState);
  const facetState: Record<string, boolean> = useMemo(
    () => facetsState?.[facet.id],
    [facet.id, facetsState]
  );

  const facetsConfig = useExistingFacetsPanelStore(
    (state) => state.facetsConfig
  );
  const facetConfig = facetsConfig?.[facet.id];

  const facetStateRef = useRef(facetState);
  facetStateRef.current = facetState;

  function getSelectedValues(): string[] {
    return Object.keys(facetStateRef.current || {});
  }

  /** This variable stores placeholders for facet options that are selected, but don't exist.
   * For example, if user selects "foo" and "bar" options, but only "foo" exists in the options list,
   * then "bar" will be added to the options list as a placeholder with 0 matches_count and will be displayed as selected for user.
   * But upon unselection, the option will disappear from the list.
   * Such behavior might happen in case when query params contained options that are not present in the current options list.
   */
  const placeholderOptions: Record<string, FacetOptionDto> = useMemo(() => {
    if (!options) {
      return {};
    }

    if (!facetState) {
      return {};
    }

    const existingOptions = new Set<string>(
      options.map((option) => valueToString(option.value))
    );

    return Object.keys(facetState)
      .filter((value) => !existingOptions.has(value))
      .map((key) => ({
        display_name: stringToValue(key),
        matches_count: 0,
        value: stringToValue(key),
      }))
      .reduce(
        (acc, current) => ({ ...acc, [current.value]: current }),
        {} as Record<string, FacetOptionDto>
      );
  }, [options, facetState]);

  const extendedOptions = useMemo(() => {
    if (!options) {
      return null;
    }

    return [...options, ...Object.values(placeholderOptions)];
  }, [options, placeholderOptions]);

  useEffect(() => {
    setIsLoaded(!!options); // Sync prop change with state

    if (isLoading && options) {
      setIsLoading(false);
    }
    // disabling as the effect has to only run on options change"
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options]);

  // Store filter value in localStorage per preset and facet
  const [filter, setFilter] = useLocalStorage<string>(
    `facet-${presetName}-${facet.id}-filter`,
    ""
  );

  const isOptionSelected = (optionValue: string) => {
    if (!facetState) {
      return true;
    }

    const strValue = valueToString(optionValue);
    return !!facetState[strValue];
  };

  const isOptionSelectable = (facetOption: FacetOptionDto) => {
    return facetOption.matches_count > 0 || !!facetConfig?.canHitEmptyState;
  };

  const handleExpandCollapse = (isOpen: boolean) => {
    setIsOpen(!isOpen);

    if (!isLoaded && !isLoading) {
      onLoadOptions && onLoadOptions();
      setIsLoading(true);
    }
  };

  function checkIfOptionExclusievlySelected(optionValue: string): boolean {
    if (!facetState) {
      return false;
    }

    return (
      getSelectedValues().length === 1 && facetState[valueToString(optionValue)]
    );
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
          facetOption.value
        )}
        isSelected={
          !!placeholderOptions[facetOption.value] ||
          (isOptionSelected(facetOption.value) &&
            isOptionSelectable(facetOption))
        }
        isSelectable={isOptionSelectable(facetOption)}
        renderLabel={
          facetConfig?.renderOptionLabel
            ? () => facetConfig.renderOptionLabel!(facetOption)
            : () => facetOption.display_name
        }
        renderIcon={
          facetConfig?.renderOptionIcon
            ? () => facetConfig.renderOptionIcon!(facetOption)
            : undefined
        }
        onToggleOption={() => toggleFacetOption(facet.id, facetOption.value)}
        onSelectOneOption={() =>
          selectOneFacetOption(facet.id, facetOption.value)
        }
        onSelectAllOptions={() => selectAllFacetOptions(facet.id)}
      />
    );
  }

  function renderBody() {
    if (
      facetOptionsLoadingState[facet.id] === "loading" ||
      !Object.keys(facetOptionsLoadingState).length
    ) {
      return Array.from({ length: 3 }).map((_, index) =>
        renderSkeleton(`skeleton-${index}`)
      );
    }

    let optionsToRender =
      extendedOptions
        ?.filter((facetOption) =>
          facetOption.display_name
            .toLocaleLowerCase()
            .includes(filter.toLocaleLowerCase())
        )
        .sort((fst, scd) => scd.matches_count - fst.matches_count) || [];

    if (facetConfig?.sortCallback) {
      const sortCallback = facetConfig.sortCallback as any;
      optionsToRender = optionsToRender.sort((fst, scd) =>
        sortCallback(scd) > sortCallback(fst) ? 1 : -1
      );
    }

    if (!optionsToRender.length) {
      return (
        <div className="px-2 py-1 text-sm text-gray-500 italic">
          No matching values found
        </div>
      );
    }

    return optionsToRender.map((facetOption, index) =>
      renderFacetValue(facetOption, index)
    );
  }

  return (
    <div data-testid="facet" className="pb-2 border-b border-gray-200">
      <div
        className="relative lex items-center justify-between px-2 py-2 cursor-pointer hover:bg-gray-50"
        onClick={() => handleExpandCollapse(isOpen)}
      >
        <div className="flex items-center space-x-2">
          <Icon className="size-5 -m-0.5 text-gray-600" />
          {isLoading && <Skeleton containerClassName="h-4 w-20" />}
          {!isLoading && <Title className="text-sm">{facet.name}</Title>}
        </div>
        {!facet.is_static && (
          <button
            data-testid="delete-facet"
            onClick={(mouseEvent) => {
              mouseEvent.preventDefault();
              mouseEvent.stopPropagation();
              onDelete && onDelete();
            }}
            className="absolute right-2 top-2 p-1 text-gray-400 hover:text-gray-600"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        )}
      </div>

      {isOpen && (
        <div>
          {options && options.length >= 10 && (
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
          <div
            className={`max-h-60 overflow-y-auto${facetOptionsLoadingState[facet.id] === "reloading" ? " pointer-events-none opacity-70" : ""}`}
          >
            {renderBody()}
          </div>
        </div>
      )}
    </div>
  );
};
