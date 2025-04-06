import React, { useState } from "react";
import { AreaChart, Card } from "@tremor/react";
import { AlertDashboardData } from "./types";
import { AlertDto } from "@/entities/alerts/model";

interface GridItemProps {
  item: AlertDashboardData;
  alert: AlertDto;
}

const GridItem: React.FC<GridItemProps> = ({ item, alert }) => {
  function capitalizeFirstLetter(str: string) {
    if (!str) return str;
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  function getAlertProperty<T extends Record<string, any>>(
    obj: T,
    path: string
  ): any {
    return path
      .split(".")
      .reduce(
        (acc, key) => (acc && acc[key] !== undefined ? acc[key] : undefined),
        obj
      );
  }
  return (
    // <Card className="relative w-full h-full p-4 rounded-2xl">
    // <div className={`flex-none flex items-center justify-between p-2 h-1/5`}>
    //   <span className={`text-lg font-semibold truncate grid-item__widget`}>
    //     {capitalizeFirstLetter(item.name)}
    //   </span>
    // </div>
    <div className="flex-1 h-4/5 flex items-center justify-start grid-item__widget">
      <p className="truncate w-full">
        <span className="font-bold">{capitalizeFirstLetter(item.name)}: </span>
        <span className="truncate">
          {getAlertProperty(alert, item.name) ?? "—— ——"}
        </span>
      </p>
    </div>
    // {/* </Card> */}
  );
};

export default GridItem;
