import React, { useState } from "react";
import { WidgetData } from "../../types";
import AlertQuality from "@/app/(keep)/dashboard/alert-quality-table";

interface GridItemProps {
  item: WidgetData;
}

const GridItem: React.FC<GridItemProps> = ({ item }) => {
  const [filters, setFilters] = useState({
    ...(item?.genericMetrics?.meta?.defaultFilters || {}),
  });

  function renderGenericMetrics() {
    switch (item?.genericMetrics?.key) {
      case "alert_quality":
        return (
          <AlertQuality
            isDashBoard={true}
            filters={filters}
            setFilters={setFilters}
          />
        );

      default:
        return null;
    }
  }

  return <div className="w-full h-[90%]">{renderGenericMetrics()}</div>;
};

export default GridItem;
