import React from "react";
import GridItem from "./GridItem";
import { WidgetData } from "./types";

interface GridItemContainerProps {
  item: WidgetData;
  onEdit: (id: string) => void;
}

const GridItemContainer: React.FC<GridItemContainerProps> = ({ item, onEdit }) => {
  return (
    <GridItem item={item} onEdit={() => onEdit(item.i)} />
  );
};

export default GridItemContainer;
