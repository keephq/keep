import React from "react";
import { AreaChart } from "@tremor/react";
import { WidgetData } from "../../types";

interface GridItemProps {
  item: WidgetData;
}

const GridItem: React.FC<GridItemProps> = ({ item }) => {
  return (
    <div
      className={
        'h-56 w-full "flex-1 flex items-center justify-center grid-item__widget'
      }
    >
      <div className={"w-[100%]"}>
        <AreaChart
          className="h-56"
          data={item.metric?.data as any[]}
          index="timestamp"
          categories={[item.metric?.id === "mttr" ? "mttr" : "number"]}
          valueFormatter={(number: number) =>
            `${Intl.NumberFormat().format(number).toString()}`
          }
          startEndOnly
          connectNulls
          showLegend={false}
          showTooltip={true}
          xAxisLabel="Timestamp"
        />
      </div>
    </div>
  );
};

export default GridItem;
