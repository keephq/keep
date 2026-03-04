import { useState } from "react";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/20/solid";
import { Text } from "@tremor/react";
import { SeverityMappingConfig } from "@/entities/alerts/model/useSeverityMapping";

interface SeverityMappingFacetProps {
  config: SeverityMappingConfig;
  onCelChange: (cel: string) => void;
}

export function SeverityMappingFacet({
  config,
  onCelChange,
}: SeverityMappingFacetProps) {
  const [isOpen, setIsOpen] = useState(true);
  const mappingEntries = Object.entries(config.mappings);
  const [selected, setSelected] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(mappingEntries.map(([value]) => [value, true]))
  );

  const allSelected = mappingEntries.every(([value]) => selected[value]);
  const exclusivelySelected = (value: string) => {
    const selectedValues = mappingEntries.filter(([v]) => selected[v]);
    return selectedValues.length === 1 && selected[value];
  };

  const buildCel = (newSelected: Record<string, boolean>) => {
    const unchecked = mappingEntries.filter(([value]) => !newSelected[value]);
    if (unchecked.length === 0) {
      return "";
    }
    // Filter OUT unchecked values
    const conditions = unchecked.map(
      ([value]) => `${config.sourceField} != "${value}"`
    );
    return conditions.join(" && ");
  };

  const toggle = (value: string) => {
    const newSelected = { ...selected, [value]: !selected[value] };
    setSelected(newSelected);
    onCelChange(buildCel(newSelected));
  };

  const selectOnly = (value: string) => {
    const newSelected = Object.fromEntries(
      mappingEntries.map(([v]) => [v, v === value])
    );
    setSelected(newSelected);
    onCelChange(buildCel(newSelected));
  };

  const selectAll = () => {
    const newSelected = Object.fromEntries(
      mappingEntries.map(([v]) => [v, true])
    );
    setSelected(newSelected);
    onCelChange("");
  };

  if (!config.enabled || mappingEntries.length === 0) {
    return null;
  }

  return (
    <div className="mb-1">
      <div
        className="flex items-center gap-1 py-1.5 cursor-pointer select-none"
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? (
          <ChevronDownIcon className="h-4 w-4 text-tremor-content" />
        ) : (
          <ChevronRightIcon className="h-4 w-4 text-tremor-content" />
        )}
        <span className="text-tremor-default font-medium text-tremor-content-emphasis capitalize truncate">
          {config.sourceField}
        </span>
      </div>

      {isOpen && (
        <div>
          {mappingEntries.map(([value, color]) => {
            const isChecked = selected[value];
            const isExclusive = exclusivelySelected(value);

            return (
              <div
                key={value}
                className="flex items-center px-2 py-1 h-7 hover:bg-gray-100 rounded-sm cursor-pointer group"
                onClick={() => toggle(value)}
              >
                <div className="flex items-center min-w-[24px]">
                  <input
                    type="checkbox"
                    readOnly
                    checked={isChecked}
                    style={{ accentColor: "#eb6221" }}
                    className="h-4 w-4 rounded border-gray-300 cursor-pointer"
                  />
                </div>

                <div
                  className="flex-1 flex items-center min-w-0 gap-1"
                  title={value}
                >
                  <div className="flex items-center">
                    <div
                      className="w-1 h-4 rounded-lg"
                      style={{ backgroundColor: color }}
                    />
                  </div>
                  <Text className="truncate flex-1" title={value}>
                    {value}
                  </Text>
                </div>

                <div className="flex-shrink-0 w-8 text-right flex justify-end">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (isExclusive) {
                        selectAll();
                      } else {
                        selectOnly(value);
                      }
                    }}
                    className="h-full text-xs text-orange-600 hidden hover:text-orange-800 group-hover:block"
                  >
                    {isExclusive ? "All" : "Only"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
