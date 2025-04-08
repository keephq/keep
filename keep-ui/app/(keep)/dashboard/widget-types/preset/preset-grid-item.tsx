import React, { useMemo } from "react";
import { WidgetData, WidgetType } from "../../types";
import { usePresetAlertsCount } from "@/features/presets/custom-preset-links";
import { useDashboardPreset } from "@/utils/hooks/useDashboardPresets";
import { Button, Icon } from "@tremor/react";
import { FireIcon } from "@heroicons/react/24/outline";
import { DynamicImageProviderIcon } from "@/components/ui";
import { getStatusColor, getStatusIcon } from "@/shared/lib/status-utils";
import { SeverityBorderIcon, UISeverity } from "@/shared/ui";
import { severityMapping } from "@/entities/alerts/model";
import * as Tooltip from "@radix-ui/react-tooltip";

interface GridItemProps {
  item: WidgetData;
}

const PresetGridItem: React.FC<GridItemProps> = ({ item }) => {
  const presets = useDashboardPreset();
  const preset = useMemo(
    () => presets.find((preset) => preset.id === item.preset?.id),
    [presets, item.preset?.id]
  );
  const presetCel = useMemo(
    () => preset?.options.find((option) => option.label === "CEL")?.value || "",
    [preset]
  );
  const {
    alerts,
    totalCount: presetAlertsCount,
    isLoading,
  } = usePresetAlertsCount(
    presetCel,
    !!preset?.counter_shows_firing_only,
    5,
    0
  );

  const getColor = () => {
    let color = "#000000";
    if (
      item.widgetType === WidgetType.PRESET &&
      item.thresholds &&
      item.preset
    ) {
      for (let i = item.thresholds.length - 1; i >= 0; i--) {
        if (item.preset && presetAlertsCount >= item.thresholds[i].value) {
          color = item.thresholds[i].color;
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

  function renderCEL() {
    return (
      <Tooltip.Provider>
        <Tooltip.Root>
          <Tooltip.Trigger asChild>
            <div className="border py-0.5 px-1 rounded-md text-orange-500 truncate">
              {presetCel}
            </div>
          </Tooltip.Trigger>
          <Tooltip.Portal>
            <Tooltip.Content sideOffset={5}>
              <div className="bg-white invert-dark-mode border py-0.5 px-1 rounded-md text-orange-500">
                {presetCel}
              </div>
              <Tooltip.Arrow />
            </Tooltip.Content>
          </Tooltip.Portal>
        </Tooltip.Root>
      </Tooltip.Provider>
    );
  }

  function renderAlertsCountText() {
    return preset?.counter_shows_firing_only
      ? "Firing alerts count:"
      : "Alerts count:";
  }

  return (
    <div className="flex flex-col overflow-y-auto gap-2">
      <div className="flex-col whitespace-nowrap">
        <div className="flex gap-1 items-center">
          <div>Preset name:</div>
          <div className="truncate">{preset?.name}</div>
        </div>
        <div className="flex gap-1 items-center">
          <div>Preset CEL:</div>
          {renderCEL()}
        </div>
        <div className="flex gap-1 items-center">
          <div>{renderAlertsCountText()}</div>
          <div
            className="flex items-center text-base font-bold"
            style={{ color: getColor() }}
          >
            {preset?.counter_shows_firing_only && (
              <Icon
                className="p-0"
                style={{ color: getColor() }}
                size={"md"}
                icon={FireIcon}
              ></Icon>
            )}
            <span>{presetAlertsCount}</span>
          </div>
        </div>
      </div>
      <div
        style={{ background: hexToRgb(getColor(), 0.1) }}
        className="bg-opacity-25 flex flex-col overflow-y-auto overflow-x-hidden auto-rows-auto border rounded-md p-2"
      >
        {alerts?.map((alert) => (
          <div className="flex flex-row min-h-7 h-7 items-center gap-2">
            <SeverityBorderIcon
              severity={
                (severityMapping[Number(alert.severity)] ||
                  alert.severity) as UISeverity
              }
            />
            <Icon
              icon={getStatusIcon(alert.status)}
              size="sm"
              color={getStatusColor(alert.status)}
              className="!p-0"
            />
            <div key={alert.id + 3}>
              <DynamicImageProviderIcon
                className="inline-block"
                alt={(alert as any).providerType}
                height={16}
                width={16}
                title={(alert as any).providerType}
                providerType={(alert as any).providerType}
                src={`/icons/${(alert as any).providerType}-icon.png`}
              />
            </div>
            <div
              key={alert.id + 1}
              className="flex-1 truncate text-xs"
              title={alert.name}
            >
              {alert.name}
            </div>
            <div
              key={alert.id + 2}
              className="flex-1 truncate text-xs"
              title={alert.description}
            >
              {alert.description}
            </div>
          </div>
        ))}
      </div>
      <div className="flex justify-end">
        <Button color="orange" variant="secondary" size="xs">
          Go to widget
        </Button>
      </div>
    </div>
  );
};

export default PresetGridItem;
