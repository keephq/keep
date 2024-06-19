import React from "react";
import { Card } from "@tremor/react";
import MenuButton from "./MenuButton";
import { WidgetData } from "./types";


interface GridItemProps {
  item: WidgetData;
  onEdit: () => void;
}

const GridItem: React.FC<GridItemProps> = ({ item, onEdit }) => {
  return (
    <Card className="relative w-full h-full p-4">
      <div className="absolute top-0 left-0 right-0 p-2 z-10 flex items-center justify-between grid-item__title">
        <span className="text-lg font-semibold truncate">{item.name}</span>
        <MenuButton onEdit={onEdit} />
      </div>
      <div className="flex items-center justify-center h-full">
        <div className="text-4xl font-bold">10</div>
      </div>
    </Card>
  );
};

export default GridItem;
