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
    <Card className="relative w-full h-full p-3">
      <div className="flex flex-col h-full px-2">
        <div className={`flex-none flex items-center justify-between`}>
          <span className="text-lg font-bold truncate grid-item__widget">
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
