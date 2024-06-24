import React from "react";
import GridItem from "./GridItem";
import { WidgetData } from "./types";

interface GridItemContainerProps {
  item: WidgetData;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
}

const GridItemContainer: React.FC<GridItemContainerProps> = ({ item, onEdit, onDelete }) => {
  return (
    <GridItem item={item} onEdit={() => onEdit(item.i)} onDelete={() => onDelete(item.i)}/>
  );
};

export default GridItemContainer;
