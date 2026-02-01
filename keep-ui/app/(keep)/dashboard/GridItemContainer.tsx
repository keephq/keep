import React from "react";
import GridItem from "./GridItem";
import { WidgetData } from "./types";

interface GridItemContainerProps {
  item: WidgetData;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
  onSave: (updateItem: WidgetData) => void;
}

const GridItemContainer: React.FC<GridItemContainerProps> = ({
  item,
  onEdit,
  onDelete,
  onSave,
}) => {
  return (
    <GridItem
      item={item}
      onEdit={() => onEdit(item.i)}
      onDelete={() => onDelete(item.i)}
      onSave={onSave}
    />
  );
};

export default GridItemContainer;
