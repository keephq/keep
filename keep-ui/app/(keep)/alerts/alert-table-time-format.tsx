import React from "react";
import { format, formatRelative } from "date-fns";
import TimeAgo from "react-timeago";
import { ClockIcon, CheckIcon } from "@heroicons/react/24/outline";

// Type definition for time format options
export type TimeFormatOption =
  | "timeago"
  | "iso"
  | "local"
  | "relative"
  | "date";

/**
 * Formats a date/time value according to the specified format option
 */
export const formatDateTime = (
  dateValue: string | Date,
  formatOption: TimeFormatOption = "timeago"
) => {
  const date = dateValue instanceof Date ? dateValue : new Date(dateValue);

  if (isNaN(date.getTime())) {
    return "Invalid date";
  }

  switch (formatOption) {
    case "timeago":
      return <TimeAgo date={date} />;

    case "iso":
      return date.toISOString();

    case "local":
      return date.toLocaleString();

    case "relative":
      return formatRelative(date, new Date());

    case "date":
      return format(date, "PP"); // Format like "Mar 1, 2023"

    default:
      return <TimeAgo date={date} />;
  }
};

/**
 * Returns true if the given column ID represents a date/time column
 */
export const isDateTimeColumn = (columnId: string): boolean => {
  // TODO: just find it dynamically
  const dateTimeColumns = [
    "lastReceived",
    "createdAt",
    "updatedAt",
    "firingStartTime",
  ];
  return dateTimeColumns.includes(columnId);
};

// Add this new SubMenu component that extends the existing DropdownMenu component
const TimeFormatSubMenu = ({
  columnId,
  columnTimeFormats,
  setColumnTimeFormats,
  DropdownMenu,
}: {
  columnId: string;
  columnTimeFormats: Record<string, TimeFormatOption>;
  setColumnTimeFormats: (formats: Record<string, TimeFormatOption>) => void;
  DropdownMenu: any;
}) => {
  // Function to handle format selection
  const handleFormatSelection = (format: TimeFormatOption) => {
    setColumnTimeFormats({
      ...columnTimeFormats,
      [columnId]: format,
    });
  };

  // Check if a format is active
  const isFormatActive = (format: TimeFormatOption) =>
    columnTimeFormats[columnId] === format ||
    (!columnTimeFormats[columnId] && format === "timeago");

  return (
    <DropdownMenu.Menu
      icon={ClockIcon}
      label="Format time"
      nested={true}
      iconClassName="text-gray-900 group-hover:text-orange-500"
    >
      <DropdownMenu.Item
        label="Time ago (e.g. 5 minutes ago)"
        icon={isFormatActive("timeago") ? CheckIcon : undefined}
        onClick={() => handleFormatSelection("timeago")}
      />
      <DropdownMenu.Item
        label="ISO format (e.g. 2023-03-01T12:30:45Z)"
        icon={isFormatActive("iso") ? CheckIcon : undefined}
        onClick={() => handleFormatSelection("iso")}
      />
      <DropdownMenu.Item
        label="Local format (e.g. 3/1/2023, 12:30:45 PM)"
        icon={isFormatActive("local") ? CheckIcon : undefined}
        onClick={() => handleFormatSelection("local")}
      />
      <DropdownMenu.Item
        label="Relative format (e.g. Today at 12:30 PM)"
        icon={isFormatActive("relative") ? CheckIcon : undefined}
        onClick={() => handleFormatSelection("relative")}
      />
      <DropdownMenu.Item
        label="Date only (e.g. Mar 1, 2023)"
        icon={isFormatActive("date") ? CheckIcon : undefined}
        onClick={() => handleFormatSelection("date")}
      />
    </DropdownMenu.Menu>
  );
};

/**
 * Time format menu items for dropdown menu
 * This function creates a submenu for time formats
 */
export const createTimeFormatMenuItems = (
  columnId: string,
  columnTimeFormats: Record<string, TimeFormatOption>,
  setColumnTimeFormats: (formats: Record<string, TimeFormatOption>) => void,
  DropdownMenu: any
) => {
  return (
    <TimeFormatSubMenu
      columnId={columnId}
      columnTimeFormats={columnTimeFormats}
      setColumnTimeFormats={setColumnTimeFormats}
      DropdownMenu={DropdownMenu}
    />
  );
};
