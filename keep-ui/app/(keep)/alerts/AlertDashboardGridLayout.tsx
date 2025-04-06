import React from "react";
import { Responsive, WidthProvider, Layout } from "react-grid-layout";
import GridItemContainer from "./GridItemContainer";
import { AlertDashboardData, LayoutItem } from "./types";
import "react-grid-layout/css/styles.css";
import { AlertDto } from "@/entities/alerts/model";
import GridItem from "./GridItem";

const ResponsiveGridLayout = WidthProvider(Responsive);

interface GridLayoutProps {
  layout: LayoutItem[];
  onLayoutChange: (layout: LayoutItem[]) => void;
  data: AlertDashboardData[];
  alert: AlertDto;
  // onEdit: (id: string) => void;
  // onDelete: (id: string) => void;
  // onSave: (updateItem: AlertDashboardData) => void;
}

const AlertDashboardGridLayout: React.FC<GridLayoutProps> = ({
  layout,
  onLayoutChange,
  data,
  alert,
  // onEdit,
  // onDelete,
  // onSave,
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
            static: item.static ?? false,
          }));
          onLayoutChange(updatedLayout as LayoutItem[]);
        }}
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 10, sm: 11, xs: 6, xxs: 4 }}
        rowHeight={10}
        containerPadding={[0, 0]}
        margin={[5, 5]}
        useCSSTransforms={true}
        isDraggable={true}
        isResizable={true}
        compactType={null}
        draggableHandle=".grid-item__widget"
      >
        {data.map((item) => (
          <div key={item.i} data-grid={item}>
            <GridItem item={item} alert={alert} />
          </div>
        ))}
      </ResponsiveGridLayout>
    </>
  );
};

export default AlertDashboardGridLayout;
