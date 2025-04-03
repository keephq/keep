import React from "react";
import { WidgetData, WidgetType } from "../../types";
import { usePresetAlertsCount } from "@/features/presets/custom-preset-links";

interface GridItemProps {
  item: WidgetData;
}

const PresetGridItem: React.FC<GridItemProps> = ({ item }) => {
  const { totalCount: presetAlertsCount } = usePresetAlertsCount(
    item.preset?.options.find((option) => option.label === "CEL")?.value || "",
    !!item.preset?.counter_shows_firing_only
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
    console.log("Ihor", {
      item,
      presetAlertsCount,
    });
    return color;
  };

  return (
    <div className="flex-1 h-4/5 flex items-center justify-center grid-item__widget">
      <div className="text-4xl font-bold" style={{ color: getColor() }}>
        {presetAlertsCount}
      </div>
    </div>
  );
};

export default PresetGridItem;
