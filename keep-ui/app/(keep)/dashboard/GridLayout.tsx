import React from "react";
import { Responsive, WidthProvider, Layout } from "react-grid-layout";
import GridItemContainer from "./GridItemContainer";
import { LayoutItem, WidgetData } from "./types";
import "react-grid-layout/css/styles.css";
import { Preset } from "@/app/(keep)/alerts/models";
import { MetricsWidget } from "@/utils/hooks/useDashboardMetricWidgets";

const ResponsiveGridLayout = WidthProvider(Responsive);

interface GridLayoutProps {
  layout: LayoutItem[];
  onLayoutChange: (layout: LayoutItem[]) => void;
  data: WidgetData[];
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
  presets: Preset[];
  onSave: (updateItem: WidgetData) => void;
  metrics: MetricsWidget[];
}

const GridLayout: React.FC<GridLayoutProps> = ({
  layout,
  onLayoutChange,
  data,
  onEdit,
  onDelete,
  onSave,
  presets,
  metrics,
}) => {
  const layouts = { lg: layout };

  return (
    <>
      <ResponsiveGridLayout
        className="layout"
        layouts={layouts}
        onLayoutChange={(currentLayout: Layout[]) => {
          const updatedLayout = currentLayout.map((item) => ({
            ...item,
            static: item.static ?? false, // Ensure static is a boolean
          }));
          onLayoutChange(updatedLayout as LayoutItem[]);
        }}
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
        rowHeight={30}
        containerPadding={[0, 0]}
        margin={[10, 10]}
        useCSSTransforms={true}
        isDraggable={true}
        isResizable={true}
        compactType={null}
        draggableHandle=".grid-item__widget"
      >
        {data.map((item) => {
          //Updating the static hardcode db value.
          if (item.preset) {
            const preset = presets?.find((p) => p?.id === item?.preset?.id);
            item.preset = {
              ...item.preset,
              alerts_count: preset?.alerts_count ?? 0,
            };
          } else if (item.metric) {
            const metric = metrics?.find((m) => m?.id === item?.metric?.id);
            if (metric) {
              item.metric = { ...metric };
            }
          }
          return (
            <div key={item.i} data-grid={item}>
              <GridItemContainer
                key={item.i}
                item={item}
                onEdit={onEdit}
                onDelete={onDelete}
                onSave={onSave}
              />
            </div>
          );
        })}
      </ResponsiveGridLayout>
    </>
  );
};

export default GridLayout;
