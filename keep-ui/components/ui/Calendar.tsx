import * as React from "react";
import { DayPicker, DateRange } from "react-day-picker";

export function cn(...classes: (string | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

interface CalendarSingleProps {
  mode: "single";
  selected?: Date;
  onSelect?: (date: Date | undefined) => void;
  className?: string;
  classNames?: Record<string, string>;
  showOutsideDays?: boolean;
}

interface CalendarRangeProps {
  mode: "range";
  selected?: DateRange;
  onSelect?: (date: DateRange | undefined) => void;
  className?: string;
  classNames?: Record<string, string>;
  showOutsideDays?: boolean;
}

type CalendarProps =
  | (CalendarSingleProps &
      Omit<
        React.ComponentProps<typeof DayPicker>,
        | "mode"
        | "selected"
        | "onSelect"
        | "className"
        | "classNames"
        | "showOutsideDays"
      >)
  | (CalendarRangeProps &
      Omit<
        React.ComponentProps<typeof DayPicker>,
        | "mode"
        | "selected"
        | "onSelect"
        | "className"
        | "classNames"
        | "showOutsideDays"
      >);

function Calendar({
  className,
  classNames,
  showOutsideDays = true,
  mode = "single",
  onSelect,
  selected,
  ...props
}: CalendarProps) {
  const [hoveredDay, setHoveredDay] = React.useState<Date | undefined>();
  const [internalSelected, setInternalSelected] = React.useState<
    Date | DateRange | undefined
  >(selected);

  React.useEffect(() => {
    setInternalSelected(selected);
  }, [selected]);

  const handleDayMouseEnter = (day: Date) => {
    setHoveredDay(day);
  };

  const handleDayMouseLeave = () => {
    setHoveredDay(undefined);
  };

  const isInHoverRange = (day: Date) => {
    if (
      !internalSelected ||
      !("from" in internalSelected) ||
      internalSelected.to ||
      !hoveredDay
    )
      return false;

    const start = internalSelected.from;
    if (!start) return false;

    const end = hoveredDay;

    return (
      (start < end && day > start && day <= end) ||
      (start > end && day < start && day >= end)
    );
  };

  const handleDaySelect = (value: Date | DateRange | undefined) => {
    setInternalSelected(value);
    if (
      mode === "single" &&
      !(value instanceof Date) &&
      "from" in (value || {})
    ) {
      (onSelect as (date: Date | undefined) => void)?.(
        (value as DateRange)?.from
      );
    } else if (mode === "range" && (value instanceof Date || !value)) {
      (onSelect as (date: DateRange | undefined) => void)?.(undefined);
    } else {
      (onSelect as any)?.(value);
    }
  };

  const dayPickerProps = {
    ...props,
    mode,
    selected: internalSelected,
    onSelect: handleDaySelect,
    onDayMouseEnter: handleDayMouseEnter,
    onDayMouseLeave: handleDayMouseLeave,
    showOutsideDays,
    className: cn("p-3", className),
    classNames: {
      months: "flex flex-col space-y-4",
      month: "space-y-4 w-full",
      caption: "flex justify-center pt-1 relative items-center",
      caption_label: "text-sm font-medium",
      nav: "space-x-1 flex items-center",
      nav_button: cn("h-7 w-7 bg-transparent p-0 opacity-50 hover:opacity-100"),
      nav_button_previous: "absolute left-1",
      nav_button_next: "absolute right-1",
      table: "w-full border-collapse space-y-1",
      head_row: "flex",
      head_cell:
        "text-muted-foreground rounded-md w-9 font-normal text-[0.8rem]",
      row: "flex w-full mt-2",
      cell: cn(
        "text-center text-sm p-0 relative",
        "[&:has([aria-selected])]:bg-accent/50",
        "first:[&:has([aria-selected])]:rounded-l-md last:[&:has([aria-selected])]:rounded-r-md",
        "[&:has(>.day-range-end)]:rounded-r-md",
        "[&:has(>.day-range-start)]:rounded-l-md",
        "[&:has(>.day-hover)]:bg-gray-100"
      ),
      day: cn(
        "h-9 w-9 p-0 font-normal relative",
        "hover:bg-gray-100",
        "focus-visible:bg-accent focus-visible:text-accent-foreground",
        "[&.day-range-start]:bg-primary [&.day-range-start]:text-primary-foreground",
        "[&.day-range-end]:bg-primary [&.day-range-end]:text-primary-foreground",
        "[&.day-range-middle]:bg-accent/50",
        "[&.day-hover]:bg-gray-100"
      ),
      day_range_start: "day-range-start",
      day_range_end: "day-range-end",
      day_selected:
        "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
      day_today: "bg-accent text-accent-foreground",
      day_outside: "text-muted-foreground opacity-50",
      day_disabled: "text-muted-foreground opacity-50",
      day_range_middle: "day-range-middle",
      day_hidden: "invisible",
      ...classNames,
    },
    modifiers: {
      ...props.modifiers,
      hover: (day: Date) => isInHoverRange(day),
      range:
        internalSelected && "from" in internalSelected && internalSelected.to
          ? [{ after: internalSelected.from, before: internalSelected.to }]
          : [],
      rangeStart:
        internalSelected && "from" in internalSelected && internalSelected.from
          ? [internalSelected.from]
          : [],
      rangeEnd:
        internalSelected && "from" in internalSelected && internalSelected.to
          ? [internalSelected.to]
          : [],
    },
    modifiersStyles: {
      ...props.modifiersStyles,
      hover: { backgroundColor: "rgb(243 244 246)" },
      range: { backgroundColor: "rgb(243 244 246)" },
      rangeStart: {
        color: "white",
        backgroundColor: "rgb(63 63 70)",
        borderTopLeftRadius: "4px",
        borderBottomLeftRadius: "4px",
      },
      rangeEnd: {
        color: "white",
        backgroundColor: "rgb(63 63 70)",
        borderTopRightRadius: "4px",
        borderBottomRightRadius: "4px",
      },
    },
  };

  return <DayPicker {...(dayPickerProps as any)} />;
}

Calendar.displayName = "Calendar";

export { Calendar };
