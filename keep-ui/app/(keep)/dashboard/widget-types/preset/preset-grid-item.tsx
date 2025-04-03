import React from "react";
import { WidgetData, WidgetType } from "../../types";
import { usePresetAlertsCount } from "@/features/presets/custom-preset-links";
import { useDashboardPreset } from "@/utils/hooks/useDashboardPresets";
import { Icon } from "@tremor/react";
import { FireIcon } from "@heroicons/react/24/outline";
import { DynamicImageProviderIcon } from "@/components/ui";

interface GridItemProps {
  item: WidgetData;
}

const PresetGridItem: React.FC<GridItemProps> = ({ item }) => {
  const presets = useDashboardPreset();
  const preset = presets.find((preset) => preset.id === item.preset?.id);
  const {
    alerts,
    totalCount: presetAlertsCount,
    isLoading,
  } = usePresetAlertsCount(
    preset?.options.find((option) => option.label === "CEL")?.value || "",
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

  console.log(alerts);

  return (
    <div className="grid grid-cols-7 overflow-y-auto overflow-x-hidden auto-rows-auto">
      {alerts?.map((alert) => (
        <>
          <div
            key={alert.id + 1}
            className="col-span-3 overflow-hidden truncate h-4"
          >
            {alert.name}
          </div>
          <div
            key={alert.id + 2}
            className="col-span-3 overflow-hidden truncate"
          >
            {alert.description}
          </div>
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
        </>
      ))}
    </div>
    // <div className="flex-1 h-4/5 flex items-center justify-center grid-item__widget">
    //   <div
    //     className="flex items-center text-4xl font-bold"
    //     style={{ color: getColor() }}
    //   >
    //     {preset?.counter_shows_firing_only && (
    //       <Icon
    //         className="p-0"
    //         style={{ color: getColor() }}
    //         size={"xl"}
    //         icon={FireIcon}
    //       ></Icon>
    //     )}
    //     <span>{presetAlertsCount}</span>
    //   </div>
    // </div>
  );
};

export default PresetGridItem;
