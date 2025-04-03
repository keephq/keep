import React from "react";
import { WidgetData, WidgetType } from "../../types";
import { usePresetAlertsCount } from "@/features/presets/custom-preset-links";
import { useDashboardPreset } from "@/utils/hooks/useDashboardPresets";
import { Icon } from "@tremor/react";
import { FireIcon } from "@heroicons/react/24/outline";

interface GridItemProps {
  item: WidgetData;
}

const PresetGridItem: React.FC<GridItemProps> = ({ item }) => {
  const presets = useDashboardPreset();
  const preset = presets.find((preset) => preset.id === item.preset?.id);
  const { totalCount: presetAlertsCount } = usePresetAlertsCount(
    preset?.options.find((option) => option.label === "CEL")?.value || "",
    !!preset?.counter_shows_firing_only
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

  return (
    <div className="flex-1 h-4/5 flex items-center justify-center grid-item__widget">
      <div
        className="flex items-center text-4xl font-bold"
        style={{ color: getColor() }}
      >
        {preset?.counter_shows_firing_only && (
          <Icon
            className="p-0"
            style={{ color: getColor() }}
            size={"xl"}
            icon={FireIcon}
          ></Icon>
        )}
        <span>{presetAlertsCount}</span>
      </div>
    </div>
  );
};

export default PresetGridItem;
