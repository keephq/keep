import React from "react";
import { CheckIcon } from "@heroicons/react/24/outline";
import { FaList } from "react-icons/fa6";
import { Badge } from "@tremor/react";

// Type definition for list format options
export type ListFormatOption =
  | "text"
  | "badges"
  | "comma"
  | "pills"
  | "count"
  | "first";

// Type for list item structure
export interface ListItem {
  severity?: string;
  name?: string;
  target?: string;
  problem?: string;
  [key: string]: any;
}

/**
 * Check if a value is a list by attempting to parse it as JSON and checking if it's an array
 */
export const isList = (value: any): boolean => {
  if (typeof value !== "string") return false;

  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) && parsed.length > 0;
  } catch (e) {
    return false;
  }
};

/**
 * Returns true if the given column contains list values
 */
export const isListColumn = (column: any): boolean => {
  // Skip certain column types that we know aren't lists
  if (!column || column.id === "checkbox" || column.id === "alertMenu") {
    return false;
  }

  // Check if any cell in this column contains a list value
  const firstRow = column.getFacetedRowModel().rows[0];
  if (!firstRow) return false;

  const value = column.getFacetedRowModel().rows[0]?.getValue(column.id);

  // If it's already an array, return true
  if (Array.isArray(value)) return value.length > 0;

  // If it's a string, try to parse it as JSON
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) && parsed.length > 0;
    } catch (e) {
      return false;
    }
  }

  return false;
};

/**
 * Parse JSON string into a list of items
 */
const parseList = (listValue: string): ListItem[] => {
  try {
    return JSON.parse(listValue);
  } catch (e) {
    console.error("Error parsing list value:", e);
    return [];
  }
};

/**
 * Extract displayable text from a list item
 */
const getItemDisplayText = (item: any): string => {
  if (typeof item === "string") return item;
  if (typeof item === "number" || typeof item === "boolean")
    return String(item);
  if (item === null || item === undefined) return "";

  if (typeof item === "object") {
    // For objects, collect all values and join them
    return Object.values(item)
      .filter((val) => val !== null && val !== undefined)
      .map((val) =>
        typeof val === "object" ? JSON.stringify(val) : String(val)
      )
      .join(" | ");
  }

  return String(item);
};

/**
 * Format a list with different display options
 */
export const formatList = (
  listValue: string | ListItem[],
  formatOption: ListFormatOption = "badges"
) => {
  if (!listValue) return null;

  const items =
    typeof listValue === "string" ? parseList(listValue) : listValue;

  if (!items || items.length === 0) return null;

  // Create tooltip text for the full value
  const tooltipText = items.map((item) => getItemDisplayText(item)).join("\n");

  switch (formatOption) {
    case "text":
      return (
        <div className="truncate" title={tooltipText}>
          {typeof listValue === "string"
            ? listValue
            : JSON.stringify(listValue)}
        </div>
      );

    case "badges":
      return (
        <div className="flex flex-wrap max-w-full gap-1" title={tooltipText}>
          {items.slice(0, 3).map((item, index) => {
            const displayText = getItemDisplayText(item);
            // Determine color based on content if possible
            let color = "blue";
            if (typeof item === "object" && item !== null) {
              if (item.severity === "Critical") color = "red";
              else if (item.severity === "Excessive") color = "orange";
            }

            return (
              <Badge
                key={`badge-${index}`}
                color={color}
                size="xs"
                className="mr-0.5 mb-0.5"
              >
                {displayText.substring(0, 25)}
                {displayText.length > 25 ? "..." : ""}
              </Badge>
            );
          })}
          {items.length > 3 && (
            <Badge color="gray" size="xs" className="mr-0.5 mb-0.5">
              +{items.length - 3} more
            </Badge>
          )}
        </div>
      );

    case "comma":
      return (
        <div className="truncate" title={tooltipText}>
          {items.map((item) => getItemDisplayText(item)).join(", ")}
        </div>
      );

    case "pills":
      return (
        <div className="flex flex-wrap max-w-full gap-1" title={tooltipText}>
          {items.slice(0, 5).map((item, idx) => {
            const displayText = getItemDisplayText(item);
            return (
              <Badge
                key={`pill-${idx}`}
                color="gray"
                size="xs"
                className="mr-0.5 mb-0.5 rounded-full"
              >
                {displayText.substring(0, 15)}
                {displayText.length > 15 ? "..." : ""}
              </Badge>
            );
          })}
          {items.length > 5 && (
            <span className="text-xs text-gray-500 self-center">
              +{items.length - 5} more
            </span>
          )}
        </div>
      );

    case "count":
      return (
        <div className="flex items-center" title={tooltipText}>
          <Badge
            color="gray"
            size="xs"
            className="w-6 h-6 rounded-full flex items-center justify-center p-0"
          >
            {items.length}
          </Badge>
          <span className="ml-2 text-gray-600 text-sm">items</span>
        </div>
      );

    case "first":
      const firstItem = items[0];
      const displayText = getItemDisplayText(firstItem);
      // Determine color based on content if possible
      let color = "blue";
      if (typeof firstItem === "object" && firstItem !== null) {
        if (firstItem.severity === "Critical") color = "red";
        else if (firstItem.severity === "Excessive") color = "orange";
      }

      return (
        <div className="flex items-center" title={tooltipText}>
          <Badge color={color} size="xs" className="mr-1">
            {displayText.substring(0, 25)}
            {displayText.length > 25 ? "..." : ""}
          </Badge>
          {items.length > 1 && (
            <span className="text-xs text-gray-500 ml-1">
              +{items.length - 1} more
            </span>
          )}
        </div>
      );

    default:
      return (
        <div className="flex flex-wrap max-w-full gap-1" title={tooltipText}>
          {items.slice(0, 3).map((item, index) => {
            const displayText = getItemDisplayText(item);
            // Determine color based on content if possible
            let color = "blue";
            if (typeof item === "object" && item !== null) {
              if (item.severity === "Critical") color = "red";
              else if (item.severity === "Excessive") color = "orange";
            }

            return (
              <Badge
                key={`default-${index}`}
                color={color}
                size="xs"
                className="mr-0.5 mb-0.5"
              >
                {displayText.substring(0, 25)}
                {displayText.length > 25 ? "..." : ""}
              </Badge>
            );
          })}
          {items.length > 3 && (
            <span className="text-xs text-gray-500 self-center">
              +{items.length - 3} more
            </span>
          )}
        </div>
      );
  }
};

/**
 * List format submenu component for dropdown menu
 */
const ListFormatSubMenu = ({
  columnId,
  columnListFormats,
  setColumnListFormats,
  DropdownMenu,
}: {
  columnId: string;
  columnListFormats: Record<string, ListFormatOption>;
  setColumnListFormats: (formats: Record<string, ListFormatOption>) => void;
  DropdownMenu: any;
}) => {
  // Function to handle format selection
  const handleFormatSelection = (format: ListFormatOption) => {
    setColumnListFormats({
      ...columnListFormats,
      [columnId]: format,
    });
  };

  // Check if a format is activea
  const isFormatActive = (format: ListFormatOption) => {
    // Safely check for undefined columnListFormats
    if (!columnListFormats) {
      return format === "badges"; // Default format
    }
    return (
      columnListFormats[columnId] === format ||
      (!columnListFormats[columnId] && format === "badges")
    );
  };

  return (
    <DropdownMenu.Menu
      icon={FaList}
      label="Format list"
      nested={true}
      iconClassName="text-gray-900 group-hover:text-orange-500"
    >
      <DropdownMenu.Item
        label="Text (original value)"
        icon={isFormatActive("text") ? CheckIcon : undefined}
        onClick={() => handleFormatSelection("text")}
      />
      <DropdownMenu.Item
        label="Badges (colored items with details)"
        icon={isFormatActive("badges") ? CheckIcon : undefined}
        onClick={() => handleFormatSelection("badges")}
      />
      <DropdownMenu.Item
        label="Comma-separated (text only)"
        icon={isFormatActive("comma") ? CheckIcon : undefined}
        onClick={() => handleFormatSelection("comma")}
      />
      <DropdownMenu.Item
        label="Pills (rounded items)"
        icon={isFormatActive("pills") ? CheckIcon : undefined}
        onClick={() => handleFormatSelection("pills")}
      />
      <DropdownMenu.Item
        label="Count only (show number of items)"
        icon={isFormatActive("count") ? CheckIcon : undefined}
        onClick={() => handleFormatSelection("count")}
      />
      <DropdownMenu.Item
        label="First item only (with count)"
        icon={isFormatActive("first") ? CheckIcon : undefined}
        onClick={() => handleFormatSelection("first")}
      />
    </DropdownMenu.Menu>
  );
};

/**
 * List format menu items for dropdown menu
 * This function creates a submenu for list formats
 */
export const createListFormatMenuItems = (
  columnId: string,
  columnListFormats: Record<string, ListFormatOption>,
  setColumnListFormats: (formats: Record<string, ListFormatOption>) => void,
  DropdownMenu: any
) => {
  return (
    <ListFormatSubMenu
      columnId={columnId}
      columnListFormats={columnListFormats}
      setColumnListFormats={setColumnListFormats}
      DropdownMenu={DropdownMenu}
    />
  );
};
