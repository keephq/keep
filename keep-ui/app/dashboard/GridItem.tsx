import React from "react";
import { Card } from "@tremor/react";
import MenuButton from "./MenuButton";
import { WidgetData } from "./types";
import AlertQuality from "@/app/alerts/alert-quality-table";
import { useSearchParams } from "next/navigation";
import { format, parseISO } from "date-fns";

interface GridItemProps {
  item: WidgetData;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
}

const GridItem: React.FC<GridItemProps> = ({ item, onEdit, onDelete }) => {
  const searchParams = useSearchParams();
  let timeStampParams = searchParams?.get("time_stamp") ?? "{}";
  let timeStamp: { start?: string; end?: string } = {};
  try {
    timeStamp = JSON.parse(timeStampParams as string);
  } catch (e) {
    timeStamp = {};
  }
  const getColor = () => {
    let color = "#000000";
    for (let i = item.thresholds.length - 1; i >= 0; i--) {
      if (item.preset && item.preset.alerts_count >= item.thresholds[i].value) {
        color = item.thresholds[i].color;
        break;
      }
    }
    return color;
  };

  function getGenericMterics(item: WidgetData) {
    switch (item.genericMetrics) {
      case "alert_quality":
        return <AlertQuality isDashBoard={true} />;

      default:
        return null;
    }
  }

  return (
    <Card className="relative w-full h-full p-4">
      <div className="flex flex-col h-full">
        <div
          className={`flex-none flex items-center justify-between p-2 ${
            item.preset ? "h-1/5" : "h-[10%]"
          }`}
        >
          {/* For table view we need intract with table filter and pagination.so we aare dragging the widget here */}
          <span
            className={`text-lg font-semibold truncate ${
              item.preset ? "" : "grid-item__widget"
            }`}
          >
            {item.name}
          </span>
          <MenuButton
            onEdit={() => onEdit(item.i)}
            onDelete={() => onDelete(item.i)}
          />
        </div>
        {item.preset && (
          //We can remove drag and drop style and make it same as table view. if we want to maintain consistency.
          <div className="flex-1 h-4/5 flex items-center justify-center grid-item__widget">
            <div className="text-4xl font-bold" style={{ color: getColor() }}>
              {item.preset.alerts_count}
            </div>
          </div>
        )}
        <div className="w-full h-[90%]">{getGenericMterics(item)}</div>
      </div>
    </Card>
  );
};

export default GridItem;
