import React, { useState } from "react";
import { Card } from "@tremor/react";
import MenuButton from "./MenuButton";
import { WidgetData } from "./types";
import AlertQuality from "@/app/alerts/alert-quality-table";
import { useSearchParams } from "next/navigation";

interface GridItemProps {
  item: WidgetData;
  onEdit: (id: string, updateData?: WidgetData) => void;
  onDelete: (id: string) => void;
  onSave: (updateItem: WidgetData) => void;
}

function GenericMetrics({
  item,
  filters,
  setFilters,
}: {
  item: WidgetData;
  filters: any;
  setFilters: any;
}) {
  switch (item?.genericMetrics?.key) {
    case "alert_quality":
      return (
        <AlertQuality
          isDashBoard={true}
          filters={filters}
          setFilters={setFilters}
        />
      );

    default:
      return null;
  }
}

const GridItem: React.FC<GridItemProps> = ({
  item,
  onEdit,
  onDelete,
  onSave,
}) => {
  const searchParams = useSearchParams();
  const [filters, setFilters] = useState({
    ...(item?.genericMetrics?.meta?.defaultFilters || {}),
  });
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

  function getUpdateItem() {
    let newUpdateItem = item.genericMetrics;
    if (newUpdateItem && newUpdateItem.meta) {
      newUpdateItem.meta = {
        ...newUpdateItem.meta,
        defaultFilters: filters || {},
      };
      return { ...item };
    }
    return item;
  }
  const handleEdit = () => {
    onEdit(item.i, getUpdateItem());
  };

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
            onEdit={handleEdit}
            onDelete={() => onDelete(item.i)}
            onSave={() => {
              onSave(getUpdateItem());
            }}
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
        <div className="w-full h-[90%]">
          <GenericMetrics
            item={item}
            filters={filters}
            setFilters={setFilters}
          />
        </div>
      </div>
    </Card>
  );
};

export default GridItem;
