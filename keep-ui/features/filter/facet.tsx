import { useEffect, useMemo, useRef, useState } from "react";
import { Title } from "@tremor/react";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/20/solid";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { usePathname } from "next/navigation";
import Skeleton from "react-loading-skeleton";
import { FacetValue } from "./facet-value";
import { FacetConfig, FacetDto, FacetOptionDto, FacetState } from "./models";
import { TrashIcon } from "@heroicons/react/24/outline";
import { useExistingFacetStore } from "./store";

export interface FacetProps {
  facet: FacetDto;
  isOpenByDefault?: boolean;
  options?: FacetOptionDto[];
  optionsLoading: boolean;
  optionsReloading: boolean;
  showIcon?: boolean;
  facetConfig?: FacetConfig;
  onLoadOptions?: () => void;
  onDelete?: () => void;
}

export const Facet: React.FC<FacetProps> = ({
  facet,
  options,
  showIcon = true,
  optionsLoading,
  optionsReloading,
  onLoadOptions,
  onDelete,
  facetConfig,
}) => {
  function getInitialFacetState(): Set<string> {
    if (facetConfig?.checkedByDefaultOptionValues) {
      return new Set<string>(
        facetConfig.checkedByDefaultOptionValues.map((value) =>
          valueToString(value)
        )
      );
    }

    return new Set<string>();
  }

  const pathname = usePathname();
  // Get preset name from URL
  const presetName = pathname?.split("/").pop() || "default";

  // Store open/close state in localStorage with a unique key per preset and facet
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const [isLoaded, setIsLoaded] = useState<boolean>(!!options?.length);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [facetState, setFacetState] = useState<Set<string>>(
    getInitialFacetState()
  );
  const facetStateRef = useRef(facetState);
  facetStateRef.current = facetState;
  const optionsRef = useRef(options);
  optionsRef.current = options;
  const facetRef = useRef(facet);
  facetRef.current = facet;
  const [isInitialized, setIsInitialized] = useState(false);
  const clearFiltersToken = useExistingFacetStore((s) => s.clearFiltersToken);
  const setFacetCelState = useExistingFacetStore((s) => s.setFacetCelState);

  function valueToString(value: any): string {
    if (typeof value === "string") {
      /* Escape single-quote because single-quote is used for string literal mark*/
      const optionValue = value.replace(/'/g, "\\'");
      return `'${optionValue}'`;
    } else if (value == null) {
      return "null";
    }

    return `${value}`;
  }

  useEffect(() => {
    if (isInitialized || !options) {
      return;
    }

    if (facetConfig?.checkedByDefaultOptionValues) {
      return;
    }

    setFacetState(new Set(options.map((opt) => valueToString(opt.value))));
    setIsInitialized(true);
  }, [isInitialized, setIsInitialized, options, facetConfig]);

  const currentCel = useMemo(() => {
    const values = Array.from(facetState);

    if (values.length === optionsRef.current?.length) {
      return "";
    }

    if (!values.length) {
      return "";
    }

    return `${facet.property_path} in [${values.join(", ")}]`;
  }, [facet.property_path, facetState]);

  useEffect(
    () => setFacetCelState(facet.id, currentCel),
    [setFacetCelState, facet.id, currentCel]
  );

  useEffect(() => {
    if (clearFiltersToken && facetRef.current && optionsRef.current) {
      const facetState = new Set<string>();

      if (facetConfig?.checkedByDefaultOptionValues) {
        facetConfig.checkedByDefaultOptionValues.forEach((optionValue) => {
          facetState.add(valueToString(optionValue));
        });
      } else {
        optionsRef.current.forEach((option) => {
          facetState.add(valueToString(option.value));
        });
      }

      setFacetState(facetState);
    }
  }, [clearFiltersToken, setFacetState]);

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
    const strValue = valueToString(optionValue);
    return facetState.has(strValue);
  };

  function toggleFacetOption(value: any) {
    const strValue = valueToString(value);
    if (isOptionSelected(value)) {
      facetState.delete(strValue);
    } else {
      facetState.add(strValue);
    }

    setFacetState(new Set(facetState));
  }

  function selectOneFacetOption(optionValue: string): void {
    setFacetState(new Set([valueToString(optionValue)]));
  }

  function selectAllFacetOptions() {
    Object.values(options ?? []).forEach((option) =>
      facetState.add(valueToString(option.value))
    );

    setFacetState(new Set(facetState));
  }

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

    return facetState.size === 1 && facetState.has(valueToString(optionValue));
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
        isSelected={isOptionSelected(facetOption.value)}
        isSelectable={
          facetOption.matches_count > 0 || !!facetConfig?.canHitEmptyState
        }
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
        onToggleOption={() => toggleFacetOption(facetOption.value)}
        onSelectOneOption={() => selectOneFacetOption(facetOption.value)}
        onSelectAllOptions={() => selectAllFacetOptions()}
      />
    );
  }

  function renderBody() {
    if (optionsLoading) {
      return Array.from({ length: 3 }).map((_, index) =>
        renderSkeleton(`skeleton-${index}`)
      );
    }

    let optionsToRender =
      options
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
            className={`max-h-60 overflow-y-auto${optionsReloading ? " pointer-events-none opacity-70" : ""}`}
          >
            {renderBody() as any}
          </div>
        </div>
      )}
    </div>
  );
};
