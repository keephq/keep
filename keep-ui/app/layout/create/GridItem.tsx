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
      <div className="flex flex-col h-full">
        {/* First Div: Header */}
        <div className="flex-none h-1/5 p-2 flex items-center justify-between">
          <span className="text-lg font-semibold truncate">{item.name}</span>
          <MenuButton onEdit={onEdit} />
        </div>

        {/* Second Div: Content */}
        <div className="flex-1 h-4/5 flex items-center justify-center grid-item__widget">
          <div className="text-4xl font-bold">10</div>
        </div>
      </div>
    </Card>
  );
};

export default GridItem;
