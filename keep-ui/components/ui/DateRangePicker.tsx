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
import { enUS, zhCN } from "date-fns/locale";
import { type DateRange } from "react-day-picker";
import clsx from "clsx";
import { useI18n } from "@/i18n/hooks/useI18n";
import { useLocale } from "next-intl";

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
  value: () => TimeFrame;
}

interface CategoryPreset {
  title: string;
  options: TimePreset[];
}

interface EnhancedDateRangePickerProps {
  timeFrame: TimeFrame;
  setTimeFrame: (timeFrame: TimeFrame) => void;
  className?: string;
  timeframeRefreshInterval?: number;
  disabled?: boolean;
  hasPlay?: boolean;
  hasRewind?: boolean;
  hasForward?: boolean;
  hasZoomOut?: boolean;
  enableYearNavigation?: boolean;
  pausedByDefault?: boolean;
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

/** @deprecated Use EnhancedDateRangePicker instead. Will be removed soon */
export default function EnhancedDateRangePicker({
  timeFrame,
  setTimeFrame,
  className = "",
  timeframeRefreshInterval = 1000,
  disabled = false,
  hasPlay = true,
  hasRewind = true,
  hasForward = true,
  hasZoomOut = false,
  pausedByDefault = true,
  enableYearNavigation = false,
}: EnhancedDateRangePickerProps) {
  const { t } = useI18n();
  const locale = useLocale();
  const dateFnsLocale = locale === "zh-CN" ? zhCN : enUS;
  const [isPaused, setIsPaused] = useState(timeFrame.paused ?? pausedByDefault);
  const [showCalendar, setShowCalendar] = useState(false);
  const [showMoreOptions, setShowMoreOptions] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState<TimePreset | null>(null);
  const [calendarRange, setCalendarRange] = useState<DateRange | undefined>(
    timeFrame.start && timeFrame.end
      ? {
          from: timeFrame.start,
          to: timeFrame.end,
        }
      : undefined
  );

  const quickPresets = useMemo(
    () =>
      [
        {
          badge: "15m",
          label: t("common.timeRange.past15Minutes"),
          value: () => ({
            start: new Date(Date.now() - 15 * ONE_MINUTE),
            end: new Date(),
          }),
        },
        {
          badge: "1h",
          label: t("common.timeRange.pastHour"),
          value: () => ({
            start: new Date(Date.now() - ONE_HOUR),
            end: new Date(),
          }),
        },
        {
          badge: "4h",
          label: t("common.timeRange.past4Hours"),
          value: () => ({
            start: new Date(Date.now() - 4 * ONE_HOUR),
            end: new Date(),
          }),
        },
        {
          badge: "1d",
          label: t("common.timeRange.pastDay"),
          value: () => ({
            start: new Date(Date.now() - ONE_DAY),
            end: new Date(),
          }),
        },
        {
          badge: "2d",
          label: t("common.timeRange.past2Days"),
          value: () => ({
            start: new Date(Date.now() - 2 * ONE_DAY),
            end: new Date(),
          }),
        },
        {
          badge: "3d",
          label: t("common.timeRange.past3Days"),
          value: () => ({
            start: new Date(Date.now() - 3 * ONE_DAY),
            end: new Date(),
          }),
        },
        {
          badge: "7d",
          label: t("common.timeRange.past7Days"),
          value: () => ({
            start: new Date(Date.now() - 7 * ONE_DAY),
            end: new Date(),
          }),
        },
        {
          badge: "15d",
          label: t("common.timeRange.past15Days"),
          value: () => ({
            start: new Date(Date.now() - 15 * ONE_DAY),
            end: new Date(),
          }),
        },
        {
          badge: "30d",
          label: t("common.timeRange.past30Days"),
          value: () => ({
            start: new Date(Date.now() - 30 * ONE_DAY),
            end: new Date(),
          }),
        },
        {
          badge: "all",
          label: t("common.timeRange.allTime"),
          value: () => ({
            start: null,
            end: null,
            paused: true,
          }),
        },
      ] as TimePreset[],
    [t]
  );

  const categories = useMemo<CategoryPreset[]>(
    () => [
      {
        title: t("common.timeRange.relativeTime"),
        options: [
          {
            badge: "30m",
            label: t("common.timeRange.past30Minutes"),
            value: () => ({
              start: new Date(Date.now() - 30 * ONE_MINUTE),
              end: new Date(),
            }),
          },
          {
            badge: "45m",
            label: t("common.timeRange.past45Minutes"),
            value: () => ({
              start: new Date(Date.now() - 45 * ONE_MINUTE),
              end: new Date(),
            }),
          },
          {
            badge: "2h",
            label: t("common.timeRange.past2Hours"),
            value: () => ({
              start: new Date(Date.now() - 2 * ONE_HOUR),
              end: new Date(),
            }),
          },
          {
            badge: "6h",
            label: t("common.timeRange.past6Hours"),
            value: () => ({
              start: new Date(Date.now() - 6 * ONE_HOUR),
              end: new Date(),
            }),
          },
          {
            badge: "6d",
            label: t("common.timeRange.past6Days"),
            value: () => ({
              start: new Date(Date.now() - 6 * ONE_DAY),
              end: new Date(),
            }),
          },
          {
            badge: "60d",
            label: t("common.timeRange.past60Days"),
            value: () => ({
              start: new Date(Date.now() - 60 * ONE_DAY),
              end: new Date(),
            }),
          },
        ],
      },
      {
        title: t("common.timeRange.fixedTime"),
        options: [
          {
            badge: "today",
            label: t("common.timeRange.today"),
            value: () => ({
              start: new Date(new Date().setHours(0, 0, 0, 0)),
              end: new Date(),
            }),
          },
          {
            badge: "week",
            label: t("common.timeRange.thisWeek"),
            value: () => ({
              start: new Date(
                new Date().setDate(new Date().getDate() - new Date().getDay())
              ),
              end: new Date(),
            }),
          },
        ],
      },
    ],
    [t]
  );

  // set initial preset and notify parent
  useEffect(() => {
    setTimeout(() => {
      handlePresetSelect(
        quickPresets.find((preset) => preset.badge === "all") as TimePreset,
        pausedByDefault
      );
    }, 100);
  }, []);

  const handlePresetSelect = (preset: TimePreset, isPaused = true) => {
    setSelectedPreset(preset);
    setTimeFrame({
      ...preset.value(),
      paused: isPaused,
      isFromCalendar: false,
    });
    setIsPaused(isPaused);
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
          setTimeFrame({
            start: null,
            end: null,
            paused: false,
          });
          return;
        }
        const duration = timeFrame.end.getTime() - timeFrame.start.getTime();
        setTimeFrame({
          start: new Date(Date.now() - duration),
          end: new Date(),
          paused: false,
        });
      }, timeframeRefreshInterval);
    }
    return () => clearInterval(interval);
  }, [isPaused, timeFrame, setTimeFrame, timeframeRefreshInterval]);

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

  const getSelectedOptionText = () => {
    if (!selectedPreset) {
      return quickPresets.find((preset) => preset.badge === "all")?.label;
    }

    if (!isPaused && selectedPreset) {
      return selectedPreset.label;
    }

    if (!timeFrame.start || !timeFrame.end) {
      return t("common.timeRange.allTime");
    }

    return `${format(timeFrame.start, "MMM d, yyyy HH:mm", {
      locale: dateFnsLocale,
    })} - ${format(timeFrame.end, "MMM d, yyyy HH:mm", {
      locale: dateFnsLocale,
    })}`;
  };

  const getSelectedBadgeText = () => {
    if (!isPaused || !selectedPreset) {
      return t("common.timeRange.live");
    }

    if (!timeFrame.start || !timeFrame.end) {
      return t("common.timeRange.all");
    }

    return formatDuration(timeFrame.start, timeFrame.end);
  };

  const handleCalendarSelect = (date: DateRange | Date | undefined) => {
    if (date && "from" in date) {
      setCalendarRange(date);
      if (date.from && date.to) {
        setTimeFrame({
          start: date.from,
          end: date.to,
          paused: true,
          isFromCalendar: true,
        });
        if (date.from.getTime() !== date.to.getTime()) {
          setIsPaused(true);
          setIsOpen(false);
          setShowCalendar(false);
        }
      } else if (date.from) {
        setTimeFrame({
          start: date.from,
          end: null,
          paused: true,
          isFromCalendar: true,
        });
      }
    }
  };

  return (
    <div className="flex items-center">
      <Popover.Root open={isOpen} onOpenChange={setIsOpen}>
        <Popover.Trigger asChild>
          <Button
            size="xs"
            variant="secondary"
            className={clsx(
              "justify-start rounded border-b border-gray-200 hover:bg-gray-200",
              isOpen && "rounded-b-none"
            )}
            disabled={disabled}
          >
            <div className="flex items-center w-full">
              <Badge
                color={isPaused ? "gray" : "green"}
                className={`mr-2 min-w-14 justify-center ${
                  isPaused ? "" : "bg-green-700"
                }`}
              >
                {getSelectedBadgeText()}
              </Badge>
              <span className="text-gray-900 text-left translate-y-[1px] min-w-[300px]">
                <Text>{getSelectedOptionText()}</Text>
              </span>
              <ChevronDown className="w-4 h-4 ml-auto text-gray-500" />
            </div>
          </Button>
        </Popover.Trigger>

        <Popover.Portal>
          <Popover.Content
            className="z-50 w-[var(--radix-popover-trigger-width)] -mt-px rounded-md rounded-t-none border bg-white shadow-md outline-none"
            align="start"
          >
            {!showCalendar ? (
              <div className="p-0 w-full relative">
                <div className="flex flex-col">
                  {quickPresets.map((preset, index) => (
                    <Button
                      key={index}
                      variant="secondary"
                      className="w-full justify-start rounded-none border-transparent first:rounded-t h-8 hover:bg-gray-200 px-2"
                      onClick={() => handlePresetSelect(preset)}
                    >
                      <Badge
                        color="gray"
                        className="mr-2 min-w-14 justify-center text-sm"
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
                    className="w-full justify-start rounded-none border-transparent h-8 hover:bg-gray-200 px-2"
                    onClick={() => setShowCalendar(true)}
                  >
                    <div className="flex items-center w-full">
                      <Badge
                        color="gray"
                        className="mr-2 min-w-14 justify-center"
                      >
                        <CalendarIcon size={16} />
                      </Badge>
                      <span className="text-gray-900 text-sm">
                        {t("common.timeRange.selectFromCalendar")}
                      </span>
                    </div>
                  </Button>

                  <Button
                    variant="secondary"
                    className="w-full justify-start rounded-none border-transparent last:rounded-b h-8 hover:bg-gray-200 px-2"
                    onClick={() => setShowMoreOptions(!showMoreOptions)}
                  >
                    <div className="flex items-center w-full">
                      <Badge
                        color="gray"
                        className="mr-2 min-w-14 justify-center"
                      >
                        <ChevronRight size={16} />
                      </Badge>
                      <span className="text-gray-900 text-sm">
                        {t("common.timeRange.moreOptions")}
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
                              className="cursor-pointer transition-colors text-sm"
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
                  onSelect={handleCalendarSelect}
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

      <div className="flex items-center relative z-0 gap-x-2 ml-2 h-full">
        <div className="flex h-full">
          {hasPlay && (
            <Button
              size="xs"
              color="gray"
              variant="secondary"
              className="justify-start rounded-none first:rounded-l last:rounded-r border-b border-gray-200 h-full"
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
              className="justify-start rounded-none first:rounded-l last:rounded-r border-b border-gray-200"
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
              className="justify-start rounded-none first:rounded-l last:rounded-r border-b border-gray-200"
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
            className="justify-start rounded-none first:rounded-l last:rounded-r border-b border-gray-200"
            onClick={handleZoomOut}
            disabled={disabled}
            icon={ZoomOut}
          />
        )}
      </div>
    </div>
  );
}
