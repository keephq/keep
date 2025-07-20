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

  // Get total alerts count
  const {
    totalCount: totalAlertsCount,
    isLoading: isLoadingTotal,
  } = usePresetAlertsCount(
    filterCel,
    false, // Always get total count
    0,
    0,
    10000
  );

  // Get firing alerts count
  const {
    totalCount: firingAlertsCount,
    isLoading: isLoadingFiring,
  } = usePresetAlertsCount(
    filterCel,
    true, // Get firing count
    0,
    0,
    10000
  );

  const isLoading = isLoadingTotal || isLoadingFiring;

  const router = useRouter();

  function handleGoToPresetClick() {
    router.push(`/alerts/${preset?.name.toLowerCase()}`);
  }

  const getColor = (count: number) => {
    let color = "#1f2937"; // Default dark gray instead of black
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
  const displayCount = showFiringOnly ? firingAlertsCount : totalAlertsCount;
  const count = isLoading ? "..." : displayCount;

  // Use firing count for threshold colors when showFiringOnly is selected
  const thresholdCount = showFiringOnly ? firingAlertsCount : totalAlertsCount;
  const color = getColor(thresholdCount);

  return (
    <div
      style={{ 
        background: hexToRgb(color, 0.15),
        borderColor: color,
        borderWidth: '2px'
      }}
      className="max-w-full border rounded-lg p-2 h-full shadow-sm"
    >
      <div className="flex flex-col h-full">
        {/* Header with preset name */}
        <div className="flex items-center justify-between mb-2 flex-shrink-0">
          <div className="text-xs font-semibold text-gray-800 truncate">
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

        {/* Main content area */}
        <div className="flex-1 flex flex-col justify-center min-h-0">
          {/* Alert count display */}
          <div className="text-center mb-1">
            <div 
              className="text-2xl font-black tracking-tight" 
              style={{ 
                color,
                textShadow: `0 1px 2px rgba(0,0,0,0.1)`
              }}
            >
              {isLoading ? (
                <Skeleton containerClassName="h-6 w-12 mx-auto" />
              ) : (
                count
              )}
            </div>
          </div>

          {/* Label with icon */}
          <div className="flex items-center justify-center text-xs font-medium text-gray-700 h-4">
            <span>{label}</span>
            {showFiringOnly && (
              <Icon
                className="ml-1"
                style={{ color }}
                size="xs"
                icon={FireIcon}
              />
            )}
          </div>
        </div>

        {/* Status indicator */}
        <div className="mt-1 flex justify-center flex-shrink-0 h-2">
          {!isLoading && (
            <div 
              className="w-2 h-2 rounded-full shadow-sm"
              style={{ 
                backgroundColor: color,
                boxShadow: `0 1px 2px ${hexToRgb(color, 0.3)}`
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default WidgetAlertCountPanel; 