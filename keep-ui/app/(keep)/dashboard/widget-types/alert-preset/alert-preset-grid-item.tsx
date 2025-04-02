import React from "react";
import { WidgetData, WidgetType } from "../../types";

interface GridItemProps {
  item: WidgetData;
}

const AlertPresetGridItem: React.FC<GridItemProps> = ({ item }) => {
  const getColor = () => {
    let color = "#000000";
    if (
      item.widgetType === WidgetType.PRESET &&
      item.thresholds &&
      item.preset
    ) {
      for (let i = item.thresholds.length - 1; i >= 0; i--) {
        if (
          item.preset &&
          item.preset.alerts_count >= item.thresholds[i].value
        ) {
          color = item.thresholds[i].color;
          break;
        }
      }
    }
    return color;
  };

  return (
    <div className="flex-1 h-4/5 flex items-center justify-center grid-item__widget">
      <div className="text-4xl font-bold" style={{ color: getColor() }}>
        THIS IS ALERT PRESET MONITORING
        {item.preset?.alerts_count}
      </div>
    </div>
  );
};

export default AlertPresetGridItem;
