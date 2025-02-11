import React, { useState, useEffect, useMemo } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Button, Badge, Subtitle, Text } from "@tremor/react";
import { Calendar } from "./Calendar";
import {
  Play,
  Pause,
  FastForward,
  Rewind,
  ZoomOut,
  ChevronRight,
  CalendarIcon,
  ChevronDown,
} from "lucide-react";
import { format } from "date-fns";
import { type DateRange } from "react-day-picker";

const ONE_MINUTE = 60 * 1000;
const ONE_HOUR = 60 * ONE_MINUTE;
const ONE_DAY = 24 * ONE_HOUR;

export interface TimeFrame {
  start: Date | null;
  end: Date | null;
  paused?: boolean;
  isFromCalendar?: boolean;
}
interface TimePreset {
  badge: string;
  label: string;
  value: TimeFrame;
}

interface CategoryPreset {
  title: string;
  options: TimePreset[];
}

interface EnhancedDateRangePickerProps {
  timeFrame: TimeFrame;
  setTimeFrame: (timeFrame: TimeFrame) => void;
  className?: string;
  disabled?: boolean;
  hasPlay?: boolean;
  hasRewind?: boolean;
  hasForward?: boolean;
  hasZoomOut?: boolean;
  enableYearNavigation?: boolean;
}

export function isQuickPresetRange(timeFrame: TimeFrame): boolean {
  if (!timeFrame.start || !timeFrame.end) {
    return false;
  }
  // If it's explicitly marked as from calendar, return false
  if (timeFrame.isFromCalendar) {
    return false;
  }

  const duration = timeFrame.end.getTime() - timeFrame.start.getTime();
  const endDiff = Date.now() - timeFrame.end.getTime();

  // Quick preset durations
  const quickPresetDurations = [
    15 * ONE_MINUTE, // 15m
    45 * ONE_MINUTE, // 45m
    ONE_HOUR, // 1h
    4 * ONE_HOUR, // 4h
    ONE_DAY, // 1d
    2 * ONE_DAY, // 2d
    3 * ONE_DAY, // 3d
    7 * ONE_DAY, // 7d
    15 * ONE_DAY, // 15d
    30 * ONE_DAY, // 30d
  ];

  // Check if this is a "live" or relative time range
  const isLiveRange = Math.abs(endDiff) < 1000; // End time within 1 second of now

  if (isLiveRange) {
    return quickPresetDurations.some(
      (presetDuration) => Math.abs(duration - presetDuration) < 1000 // Allow 1 second tolerance
    );
  }

  // Check if this is a fixed time range (today or this week)
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);

  const startOfWeek = new Date();
  startOfWeek.setDate(startOfWeek.getDate() - startOfWeek.getDay());
  startOfWeek.setHours(0, 0, 0, 0);

  const isToday = timeFrame.start.getTime() === startOfToday.getTime();
  const isThisWeek = timeFrame.start.getTime() === startOfWeek.getTime();

  return isToday || isThisWeek;
}

export default function EnhancedDateRangePicker({
  timeFrame,
  setTimeFrame,
  className = "",
  disabled = false,
  hasPlay = true,
  hasRewind = true,
  hasForward = true,
  hasZoomOut = false,
  enableYearNavigation = false,
}: EnhancedDateRangePickerProps) {
  const [isPaused, setIsPaused] = useState(timeFrame.paused ?? true);
  const [showCalendar, setShowCalendar] = useState(false);
  const [showMoreOptions, setShowMoreOptions] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [calendarRange, setCalendarRange] = useState<DateRange | undefined>(
    timeFrame.start && timeFrame.end
      ? {
          from: timeFrame.start,
          to: timeFrame.end,
        }
      : undefined
  );

  const quickPresets = useMemo(
    () => [
      {
        badge: "15m",
        label: "Past 15 minutes",
        value: {
          start: new Date(Date.now() - 15 * ONE_MINUTE),
          end: new Date(),
        },
      },
      {
        badge: "1h",
        label: "Past hour",
        value: {
          start: new Date(Date.now() - ONE_HOUR),
          end: new Date(),
        },
      },
      {
        badge: "4h",
        label: "Past 4 hours",
        value: {
          start: new Date(Date.now() - 4 * ONE_HOUR),
          end: new Date(),
        },
      },
      {
        badge: "1d",
        label: "Past day",
        value: {
          start: new Date(Date.now() - ONE_DAY),
          end: new Date(),
        },
      },
      {
        badge: "2d",
        label: "Past 2 days",
        value: {
          start: new Date(Date.now() - 2 * ONE_DAY),
          end: new Date(),
        },
      },
      {
        badge: "3d",
        label: "Past 3 days",
        value: {
          start: new Date(Date.now() - 3 * ONE_DAY),
          end: new Date(),
        },
      },
      {
        badge: "7d",
        label: "Past 7 days",
        value: {
          start: new Date(Date.now() - 7 * ONE_DAY),
          end: new Date(),
        },
      },
      {
        badge: "15d",
        label: "Past 15 days",
        value: {
          start: new Date(Date.now() - 15 * ONE_DAY),
          end: new Date(),
        },
      },
      {
        badge: "30d",
        label: "Past 30 days",
        value: {
          start: new Date(Date.now() - 30 * ONE_DAY),
          end: new Date(),
        },
      },
      {
        badge: "all",
        label: "All time",
        value: {
          start: null,
          end: null,
          paused: true,
        },
      },
    ],
    []
  );

  const categories = useMemo<CategoryPreset[]>(
    () => [
      {
        title: "Relative Time",
        options: [
          {
            badge: "30m",
            label: "Past 30 minutes",
            value: {
              start: new Date(Date.now() - 30 * ONE_MINUTE),
              end: new Date(),
            },
          },
          {
            badge: "45m",
            label: "Past 45 minutes",
            value: {
              start: new Date(Date.now() - 45 * ONE_MINUTE),
              end: new Date(),
            },
          },
          {
            badge: "2h",
            label: "Past 2 hours",
            value: {
              start: new Date(Date.now() - 2 * ONE_HOUR),
              end: new Date(),
            },
          },
          {
            badge: "6h",
            label: "Past 6 hours",
            value: {
              start: new Date(Date.now() - 6 * ONE_HOUR),
              end: new Date(),
            },
          },
          {
            badge: "6d",
            label: "Past 6 days",
            value: {
              start: new Date(Date.now() - 6 * ONE_DAY),
              end: new Date(),
            },
          },
          {
            badge: "60d",
            label: "Past 60 days",
            value: {
              start: new Date(Date.now() - 60 * ONE_DAY),
              end: new Date(),
            },
          },
        ],
      },
      {
        title: "Fixed Time",
        options: [
          {
            badge: "today",
            label: "Today",
            value: {
              start: new Date(new Date().setHours(0, 0, 0, 0)),
              end: new Date(),
            },
          },
          {
            badge: "week",
            label: "This Week",
            value: {
              start: new Date(
                new Date().setDate(new Date().getDate() - new Date().getDay())
              ),
              end: new Date(),
            },
          },
        ],
      },
    ],
    []
  );

  const handlePresetSelect = (preset: TimePreset) => {
    setTimeFrame({
      ...preset.value,
      paused: true,
      isFromCalendar: false,
    });
    setIsPaused(true);
    setIsOpen(false);
    setSelectedCategory(null);
    setShowMoreOptions(false);
  };

  const togglePlayPause = () => {
    setIsPaused(!isPaused);
    setTimeFrame({
      ...timeFrame,
      paused: !isPaused,
    });
  };

  const handleRewind = () => {
    if (!timeFrame.start || !timeFrame.end) {
      return;
    }
    const duration = timeFrame.end.getTime() - timeFrame.start.getTime();
    setTimeFrame({
      start: new Date(timeFrame.start.getTime() - duration),
      end: new Date(timeFrame.start.getTime()),
      paused: true,
    });
    setIsPaused(true);
  };

  const handleForward = () => {
    if (!timeFrame.start || !timeFrame.end) {
      return;
    }
    const duration = timeFrame.end.getTime() - timeFrame.start.getTime();
    setTimeFrame({
      start: new Date(timeFrame.end.getTime()),
      end: new Date(timeFrame.end.getTime() + duration),
      paused: true,
    });
    setIsPaused(true);
  };

  const handleZoomOut = () => {
    if (!timeFrame.start || !timeFrame.end) {
      return;
    }
    const duration = timeFrame.end.getTime() - timeFrame.start.getTime();
    setTimeFrame({
      start: new Date(timeFrame.start.getTime() - duration / 2),
      end: new Date(timeFrame.end.getTime() + duration / 2),
      paused: true,
    });
    setIsPaused(true);
  };

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (!isPaused) {
      interval = setInterval(() => {
        if (!timeFrame.start || !timeFrame.end) {
          return;
        }
        const duration = timeFrame.end.getTime() - timeFrame.start.getTime();
        setTimeFrame({
          start: new Date(Date.now() - duration),
          end: new Date(),
          paused: false,
        });
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isPaused, timeFrame, setTimeFrame]);

  useEffect(() => {
    if (!isOpen) {
      setShowCalendar(false);
      setShowMoreOptions(false);
      setSelectedCategory(null);
    }
  }, [isOpen]);

  const formatDuration = (start: Date, end: Date): string => {
    const durationMs = end.getTime() - start.getTime();
    const days = Math.floor(durationMs / (24 * 60 * 60 * 1000));
    const hours = Math.floor(
      (durationMs % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000)
    );
    const minutes = Math.floor((durationMs % (60 * 60 * 1000)) / (60 * 1000));

    if (days > 0) {
      return `${days}d`;
    } else if (hours > 0) {
      return `${hours}h`;
    } else {
      return `${minutes}m`;
    }
  };

  return (
    <div className="flex items-center">
      <Popover.Root open={isOpen} onOpenChange={setIsOpen}>
        <Popover.Trigger asChild>
          <Button
            size="xs"
            variant="secondary"
            className="justify-start rounded-none first:rounded-t border-b border-gray-200 hover:bg-gray-200"
            disabled={disabled}
          >
            <div className="flex items-center w-full">
              <Badge color="gray" className="mr-2 min-w-[4rem] justify-center">
                {!timeFrame.start || !timeFrame.end
                  ? "All"
                  : timeFrame.paused
                    ? formatDuration(timeFrame.start, timeFrame.end)
                    : "Live"}
              </Badge>
              <span className="text-gray-900 text-left translate-y-[1px] min-w-[300px]">
                <Text>
                  {!timeFrame.start || !timeFrame.end
                    ? "All time"
                    : `${format(
                        timeFrame.start,
                        "MMM d, yyyy HH:mm"
                      )} - ${format(timeFrame.end, "MMM d, yyyy HH:mm")}`}
                </Text>
              </span>
              <ChevronDown className="w-4 h-4 ml-auto text-gray-500" />
            </div>
          </Button>
        </Popover.Trigger>

        <Popover.Portal>
          <Popover.Content
            className="z-50 w-[var(--radix-popover-trigger-width)] rounded-md border bg-white shadow-md outline-none"
            align="start"
          >
            {!showCalendar ? (
              <div className="p-0 w-full relative">
                <div className="flex flex-col">
                  {quickPresets.map((preset, index) => (
                    <Button
                      key={index}
                      variant="secondary"
                      className="w-full justify-start rounded-none border-transparent first:rounded-t h-8 hover:bg-gray-200"
                      onClick={() => handlePresetSelect(preset)}
                    >
                      <Badge
                        color="gray"
                        className="mr-2 min-w-[4rem] justify-center text-sm"
                      >
                        {preset.badge}
                      </Badge>
                      <span className="text-gray-900 text-sm">
                        {preset.label}
                      </span>
                    </Button>
                  ))}

                  <Button
                    variant="secondary"
                    className="w-full justify-start rounded-none border-transparent h-8 hover:bg-gray-200"
                    onClick={() => setShowCalendar(true)}
                  >
                    <div className="flex items-center w-full">
                      <Badge
                        color="gray"
                        className="mr-2 min-w-[4rem] justify-center"
                      >
                        <CalendarIcon size={16} />
                      </Badge>
                      <span className="text-gray-900 text-sm">
                        Select from calendar...
                      </span>
                    </div>
                  </Button>

                  <Button
                    variant="secondary"
                    className="w-full justify-start rounded-none border-transparent last:rounded-b h-8 hover:bg-gray-200"
                    onClick={() => setShowMoreOptions(!showMoreOptions)}
                  >
                    <div className="flex items-center w-full">
                      <Badge
                        color="gray"
                        className="mr-2 min-w-[4rem] justify-center"
                      >
                        <ChevronRight size={16} />
                      </Badge>
                      <span className="text-gray-900 text-sm">
                        More options
                      </span>
                    </div>
                  </Button>
                </div>

                {showMoreOptions && (
                  <div className="absolute right-full top-0 w-64 border bg-white shadow-md">
                    {categories.map((category, index) => (
                      <div key={index} className="p-3">
                        <Subtitle className="text-xs text-gray-500 font-medium mb-2">
                          {category.title}
                        </Subtitle>
                        <div className="flex flex-wrap gap-1.5">
                          {category.options.map((option, optionIndex) => (
                            <Badge
                              key={optionIndex}
                              color="gray"
                              className="cursor-pointer hover:bg-gray-200 transition-colors text-sm"
                              onClick={() => handlePresetSelect(option)}
                            >
                              {option.badge}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="p-3 z-50">
                <Calendar
                  mode="range"
                  selected={calendarRange}
                  onSelect={(date: DateRange | Date | undefined) => {
                    if (date && "from" in date) {
                      setCalendarRange(date);
                      if (date.from && date.to) {
                        setTimeFrame({
                          start: date.from,
                          end: date.to,
                          paused: true,
                          isFromCalendar: true,
                        });
                        setIsPaused(true);
                        setIsOpen(false);
                        setShowCalendar(false);
                      }
                    }
                  }}
                  numberOfMonths={1}
                  disabled={{ after: new Date() }}
                  className="w-full bg-white"
                  defaultMonth={
                    timeFrame.start ? new Date(timeFrame.start) : undefined
                  }
                />
              </div>
            )}
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>

      <div className="flex items-center relative z-0 gap-x-2 ml-2">
        <div className="flex">
          {hasPlay && (
            <Button
              size="xs"
              color="gray"
              variant="secondary"
              className="justify-start rounded-none first:rounded-t border-b border-gray-200"
              onClick={togglePlayPause}
              disabled={disabled}
              icon={isPaused ? Play : Pause}
            />
          )}

          {hasRewind && (
            <Button
              size="xs"
              color="gray"
              variant="secondary"
              className="justify-start rounded-none first:rounded-t border-b border-gray-200"
              onClick={handleRewind}
              disabled={disabled}
              icon={Rewind}
            />
          )}

          {hasForward && (
            <Button
              size="xs"
              color="gray"
              variant="secondary"
              className="justify-start rounded-none first:rounded-t border-b border-gray-200"
              onClick={handleForward}
              disabled={disabled}
              icon={FastForward}
            />
          )}
        </div>

        {hasZoomOut && (
          <Button
            size="xs"
            color="gray"
            variant="secondary"
            className="justify-start rounded-none first:rounded-t border-b border-gray-200"
            onClick={handleZoomOut}
            disabled={disabled}
            icon={ZoomOut}
          />
        )}
      </div>
    </div>
  );
}
