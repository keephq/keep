import React, { useMemo } from "react";
import { BarChart, Button } from "@tremor/react";
import { usePresetAlertsCount } from "@/features/presets/custom-preset-links";
import { useDashboardPreset } from "@/utils/hooks/useDashboardPresets";
import { Threshold } from "../../types";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import { toDateObjectWithFallback } from "@/utils/helpers";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import {
  format,
  startOfHour,
  startOfDay,
  addMinutes,
  addHours,
  addDays,
} from "date-fns";

const ALERTS_FETCH_LIMIT = 5000;
const REFRESH_INTERVAL_MS = 10000;

interface WidgetAlertTimeSeriesPanelProps {
  presetName: string;
  showFiringOnly?: boolean;
  thresholds?: Threshold[];
  customLink?: string;
}

function getBucketKey(date: Date, bucketMinutes: number): string {
  const ms = date.getTime();
  const bucketMs = bucketMinutes * 60 * 1000;
  const bucketStart = new Date(Math.floor(ms / bucketMs) * bucketMs);
  if (bucketMinutes >= 60 * 24) {
    return format(startOfDay(bucketStart), "yyyy-MM-dd");
  }
  if (bucketMinutes >= 60) {
    return format(startOfHour(bucketStart), "yyyy-MM-dd HH:00");
  }
  return format(bucketStart, "yyyy-MM-dd HH:mm");
}

function buildChartData(
  alerts: { lastReceived: Date }[],
  rangeStart: Date | null,
  rangeEnd: Date | null
): { date: string; alerts: number }[] {
  let start: Date;
  let end: Date;
  if (rangeStart != null && rangeEnd != null) {
    start = rangeStart;
    end = rangeEnd;
  } else if (alerts.length > 0) {
    const times = alerts.map((a) => a.lastReceived.getTime());
    start = new Date(Math.min(...times));
    end = new Date(Math.max(...times));
  } else {
    end = new Date();
    start = new Date(end.getTime() - 24 * 60 * 60 * 1000);
  }

  const rangeMs = end.getTime() - start.getTime();
  const rangeHours = rangeMs / (60 * 60 * 1000);
  const rangeDays = rangeHours / 24;

  let bucketMinutes: number;
  if (rangeHours < 1) {
    bucketMinutes = 5;
  } else if (rangeDays < 1) {
    bucketMinutes = 60;
  } else {
    bucketMinutes = 60 * 24;
  }

  const buckets = new Map<string, number>();
  alerts.forEach((a) => {
    const key = getBucketKey(a.lastReceived, bucketMinutes);
    buckets.set(key, (buckets.get(key) ?? 0) + 1);
  });

  const result: { date: string; alerts: number }[] = [];
  const bucketMs = bucketMinutes * 60 * 1000;
  let t = new Date(Math.floor(start.getTime() / bucketMs) * bucketMs);

  while (t.getTime() <= end.getTime()) {
    const key = getBucketKey(t, bucketMinutes);
    result.push({ date: key, alerts: buckets.get(key) ?? 0 });
    if (bucketMinutes >= 60 * 24) {
      t = addDays(t, 1);
    } else if (bucketMinutes >= 60) {
      t = addHours(t, 1);
    } else {
      t = addMinutes(t, bucketMinutes);
    }
  }

  return result;
}

function hexToRgb(hex: string, alpha: number = 1) {
  hex = hex.replace(/^#/, "");
  if (hex.length === 3) {
    hex = hex
      .split("")
      .map((c) => c + c)
      .join("");
  }
  const bigint = parseInt(hex, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgb(${r}, ${g}, ${b}, ${alpha})`;
}

function getThresholdColor(
  count: number,
  thresholds: Threshold[]
): string | null {
  for (let i = thresholds.length - 1; i >= 0; i--) {
    if (count >= thresholds[i].value) {
      return thresholds[i].color;
    }
  }
  return null;
}

const WidgetAlertTimeSeriesPanel: React.FC<WidgetAlertTimeSeriesPanelProps> = ({
  presetName,
  showFiringOnly = false,
  thresholds = [],
  customLink,
}) => {
  const searchParams = useSearchParams();
  const { timeRangeCel, rangeStart, rangeEnd } = useMemo(() => {
    const timeRangeSearchParam = searchParams.get("time_stamp");
    if (timeRangeSearchParam) {
      try {
        const parsed = JSON.parse(timeRangeSearchParam);
        const startVal = parsed.start ?? parsed.from;
        const endVal = parsed.end ?? parsed.to;
        if (startVal && endVal) {
          const start = new Date(startVal);
          const end = new Date(endVal);
          if (!isNaN(start.getTime()) && !isNaN(end.getTime())) {
            return {
              timeRangeCel: `lastReceived >= "${start.toISOString()}" && lastReceived <= "${end.toISOString()}"`,
              rangeStart: start,
              rangeEnd: end,
            };
          }
        }
      } catch {
        // fall through
      }
    }
    // No dashboard time filter: query same as Alert Count Panel
    return {
      timeRangeCel: "",
      rangeStart: null as Date | null,
      rangeEnd: null as Date | null,
    };
  }, [searchParams]);

  const presets = useDashboardPreset();
  const preset = useMemo(
    () => presets.find((p) => p.name === presetName),
    [presets, presetName]
  );

  const presetCel = useMemo(
    () => preset?.options.find((option) => option.label === "CEL")?.value || "",
    [preset]
  );

  const filterCel = useMemo(
    () => [timeRangeCel, presetCel].filter(Boolean).join(" && "),
    [presetCel, timeRangeCel]
  );

  const { alerts = [], isLoading } = usePresetAlertsCount(
    filterCel,
    showFiringOnly,
    ALERTS_FETCH_LIMIT,
    0,
    REFRESH_INTERVAL_MS
  );

  const chartData = useMemo(() => {
    const normalized = alerts.map((a: { lastReceived?: string | Date }) => ({
      lastReceived: toDateObjectWithFallback(a.lastReceived ?? new Date()),
    }));
    return buildChartData(normalized, rangeStart, rangeEnd);
  }, [alerts, rangeStart, rangeEnd]);

  const thresholdColor = useMemo(
    () => getThresholdColor(alerts.length, thresholds),
    [alerts.length, thresholds]
  );

  const router = useRouter();

  function handleGoToPresetClick() {
    router.push(`/alerts/${preset?.name?.toLowerCase()}`);
  }

  function handleCustomLinkClick() {
    if (customLink) {
      window.open(customLink, "_blank");
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between mb-2 flex-shrink-0">
        <span className="text-sm font-medium text-gray-700">
          Alert count over time
          {showFiringOnly && " (firing only)"}
        </span>
        <div className="flex items-center space-x-1">
          <Button
            color="orange"
            variant="secondary"
            size="xs"
            onClick={handleGoToPresetClick}
          >
            Go to Preset
          </Button>
          {customLink && (
            <Button
              color="blue"
              variant="secondary"
              size="xs"
              onClick={handleCustomLinkClick}
            >
              Go to Link
            </Button>
          )}
        </div>
      </div>
      <div
        style={{
          background: thresholdColor
            ? hexToRgb(thresholdColor, 0.15)
            : "rgb(243 244 246 / 0.5)",
          borderWidth: thresholdColor ? "2px" : "1px",
          borderStyle: "solid",
          borderColor: thresholdColor ?? "rgb(229 231 235)",
        }}
        className="rounded-lg p-2 flex-1 min-h-[140px] flex flex-col"
      >
        {isLoading ? (
          <Skeleton className="h-full w-full flex-1" />
        ) : chartData.length === 0 ? (
          <div className="flex-1 flex items-center justify-center text-sm text-gray-500">
            No alerts in the selected time range
          </div>
        ) : (
          <div className="flex-1 min-h-[120px]">
            <BarChart
              className="h-full w-full"
              data={chartData}
              index="date"
              categories={["alerts"]}
              colors={["orange"]}
              valueFormatter={(v) => `${v}`}
              showLegend={false}
              showGridLines
              showAnimation
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default WidgetAlertTimeSeriesPanel;
