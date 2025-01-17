import { Text } from "@tremor/react";
import clsx from "clsx";

export interface FacetValueProps {
  label: string;
  count: number;
  isExclusivelySelected: boolean;
  isSelected: boolean;
  showIcon: boolean;
  renderLabel?: () => JSX.Element | string | undefined;
  renderIcon?: () => JSX.Element | undefined;
  onSelectOneOption: (value: string) => void;
  onSelectAllOptions: () => void;
  onToggleOption: (value: string) => void;
}

export const FacetValue: React.FC<FacetValueProps> = ({
  label,
  count,
  isSelected,
  isExclusivelySelected,
  showIcon = false,
  onSelectOneOption,
  onSelectAllOptions,
  onToggleOption: onSelect,
  renderIcon,
  renderLabel,
}) => {
  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSelect(label);
  };

  const handleActionClick = (e: React.MouseEvent) => {
    e.stopPropagation();

    if (isExclusivelySelected) {
      onSelectAllOptions();
    } else {
      onSelectOneOption(label);
    }
  };

  return (
    <div
      className={`flex items-center px-2 py-1 h-7 hover:bg-gray-100 rounded-sm cursor-pointer group ${!count ? "opacity-50 pointer-events-none" : ""}`}
      onClick={handleCheckboxClick}
    >
      <div className="flex items-center min-w-[24px]">
        <input
          type="checkbox"
          checked={isSelected && count > 0}
          onClick={handleCheckboxClick}
          onChange={() => {}}
          style={{ accentColor: "#eb6221" }}
          className="h-4 w-4 rounded border-gray-300 cursor-pointer"
        />
      </div>

      <div className="flex-1 flex items-center min-w-0 gap-1" title={label}>
        {showIcon && (
          <div className={clsx("flex items-center")}>
            {renderIcon && renderIcon()}
          </div>
        )}
        <Text className="truncate" title={label}>
          {renderLabel ? (
            renderLabel()
          ) : (
            <span className="capitalize">{label}</span>
          )}
        </Text>
      </div>

      <div className="flex-shrink-0 w-8 text-right flex justify-end">
        <button
          onClick={handleActionClick}
          className="text-xs text-orange-600 hover:text-orange-800 hidden group-hover:block"
        >
          {isExclusivelySelected ? "All" : "Only"}
        </button>
        {
          <Text className="text-xs text-gray-500 group-hover:hidden">
            {count}
          </Text>
        }
      </div>
    </div>
  );
};
