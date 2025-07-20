import React, { useMemo } from "react";
import { WidgetData, WidgetType, Threshold } from "../../types";
import { usePresetAlertsCount } from "@/features/presets/custom-preset-links";
import { useDashboardPreset } from "@/utils/hooks/useDashboardPresets";
import { Button, Icon } from "@tremor/react";
import { FireIcon } from "@heroicons/react/24/outline";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";

interface WidgetAlertCountPanelProps {
  presetName: string;
  showFiringOnly?: boolean;
  background?: string;
  thresholds?: Threshold[];
}

const WidgetAlertCountPanel: React.FC<WidgetAlertCountPanelProps> = ({
  presetName,
  showFiringOnly = false,
  background,
  thresholds = [],
}) => {
  const searchParams = useSearchParams();
  const timeRangeCel = useMemo(() => {
    const timeRangeSearchParam = searchParams.get("time_stamp");
    if (timeRangeSearchParam) {
      const parsedTimeRange = JSON.parse(timeRangeSearchParam);
      return `lastReceived >= "${parsedTimeRange.start}" && lastReceived <= "${parsedTimeRange.end}"`;
    }
    return "";
  }, [searchParams]);
  
  const presets = useDashboardPreset();
  const preset = useMemo(
    () => presets.find((preset) => preset.name === presetName),
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

  const {
    totalCount: presetAlertsCount,
    isLoading,
  } = usePresetAlertsCount(
    filterCel,
    showFiringOnly,
    0, // No limit for count panel
    0,
    10000 // refresh interval
  );
  
  const router = useRouter();

  function handleGoToPresetClick() {
    router.push(`/alerts/${preset?.name.toLowerCase()}`);
  }

  const getColor = (count: number) => {
    let color = "#000000";
    if (thresholds && thresholds.length > 0) {
      for (let i = thresholds.length - 1; i >= 0; i--) {
        if (count >= thresholds[i].value) {
          color = thresholds[i].color;
          break;
        }
      }
    }
    return color;
  };

  function hexToRgb(hex: string, alpha: number = 1) {
    // Remove '#' if present
    hex = hex.replace(/^#/, "");

    // Handle shorthand form (#f44 → #ff4444)
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

  const label = showFiringOnly ? "Firing Alerts" : "Total Alerts";
  const count = isLoading ? "..." : presetAlertsCount;
  const color = getColor(presetAlertsCount);

  return (
    <div
      style={{ background: background || hexToRgb(color, 0.1) }}
      className="bg-opacity-25 max-w-full border rounded-md p-4"
    >
      <div className="flex flex-col items-center justify-center text-center space-y-4">
        <div className="text-2xl font-bold" style={{ color }}>
          {isLoading ? (
            <Skeleton containerClassName="h-8 w-16" />
          ) : (
            count
          )}
        </div>
        <div className="text-sm text-gray-600">
          {label}
          {showFiringOnly && (
            <Icon
              className="ml-2 inline-block"
              style={{ color }}
              size="sm"
              icon={FireIcon}
            />
          )}
        </div>
        <div className="text-xs text-gray-500">
          {preset?.name}
        </div>
        <Button
          color="orange"
          variant="secondary"
          size="xs"
          onClick={handleGoToPresetClick}
        >
          Go to Preset
        </Button>
      </div>
    </div>
  );
};

export default WidgetAlertCountPanel; 