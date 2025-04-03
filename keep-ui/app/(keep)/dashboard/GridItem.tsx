import React, { useState } from "react";
import { Card } from "@tremor/react";
import MenuButton from "./MenuButton";
import { WidgetData } from "./types";
import PresetGridItem from "./widget-types/preset/preset-grid-item";
import MetricGridItem from "./widget-types/metric/metric-grid-item";
import GenericMetricsGridItem from "./widget-types/generic-metrics/generic-metrics-grid-item";

interface GridItemProps {
  item: WidgetData;
  onEdit: (id: string, updateData?: WidgetData) => void;
  onDelete: (id: string) => void;
  onSave: (updateItem: WidgetData) => void;
}

const GridItem: React.FC<GridItemProps> = ({
  item,
  onEdit,
  onDelete,
  onSave,
}) => {
  const [updatedItem, setUpdatedItem] = useState<WidgetData>(item);

  const handleEdit = () => {
    onEdit(updatedItem.i, updatedItem);
  };

  return (
    <Card
      className={`relative w-full h-full ${!item.metric ? "!p-4" : "!pt-0.5"}`}
    >
      <div className="flex flex-col h-full">
        <div
          className={`flex-none flex items-center justify-between p-2 ${
            item.preset ? "h-1/5" : item.metric ? "h-1/5 mb-3" : "h-[10%]"
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
              onSave(updatedItem);
            }}
          />
        </div>
        {item.preset && <PresetGridItem item={item} />}
        {item.metric && <MetricGridItem item={item} />}
        {item.genericMetrics && (
          <GenericMetricsGridItem
            item={item}
            onEdit={setUpdatedItem}
          ></GenericMetricsGridItem>
        )}
      </div>
    </Card>
  );
};

export default GridItem;
