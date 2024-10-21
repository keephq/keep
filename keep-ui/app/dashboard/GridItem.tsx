import React from "react";
import {AreaChart, Card} from "@tremor/react";
import MenuButton from "./MenuButton";
import {WidgetData, WidgetType} from "./types";

interface GridItemProps {
  item: WidgetData;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
}

const GridItem: React.FC<GridItemProps> = ({item, onEdit, onDelete}) => {

  const getColor = () => {
    if (item.widgetType === WidgetType.PRESET && item.thresholds && item.preset) {
      let color = '#000000';
      for (let i = item.thresholds.length - 1; i >= 0; i--) {
        if (item.preset.alerts_count >= item.thresholds[i].value) {
          color = item.thresholds[i].color;
          break;
        }
      }
      return color;
    }
  };


  return (
      <Card className="relative w-full h-full p-4">
        <div className="flex flex-col h-full">
          <div className="flex-none h-1/5 p-2 flex items-center justify-between">
            <span className="text-lg font-semibold truncate">{item.name}</span>
            <MenuButton onEdit={() => onEdit(item.i)} onDelete={() => onDelete(item.i)}/>
          </div>
          <div className={(item.widgetType === WidgetType.METRIC ? 'h-56 w-full ' : 'h-4/5 ') + "flex-1 flex items-center justify-center grid-item__widget"}>
            {item.widgetType === WidgetType.PRESET && item.preset ?
                <div className="text-4xl font-bold" style={{color: getColor()}}>
                  {item.preset.alerts_count}
                </div> : item.metric ?
                <div className={"w-[80%]"}>
                  <AreaChart
                      className="h-56"
                      data={item.metric?.data}
                      index="hour"
                      categories={[item.metric?.id === "mttr" ? "mttr" : "number"]}
                      valueFormatter={(number: number) =>
                          `${Intl.NumberFormat().format(number).toString()}`
                      }
                      yAxisWidth={40}
                      startEndOnly
                      connectNulls
                      showLegend={false}
                      showTooltip={true}
                      xAxisLabel="24H Activity Data"
                  />
                </div> :
                <div>
                  Something Went Wrong!
                </div>
            }
          </div>
        </div>
      </Card>
  );
};

export default GridItem;
