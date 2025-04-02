import React, { useEffect, useState } from "react";
import { WidgetData } from "../../types";
import AlertQuality from "@/app/(keep)/dashboard/alert-quality-table";

interface GridItemProps {
  item: WidgetData;
  onEdit: (updatedItem: WidgetData) => void;
}

const GenericMetricsGridItem: React.FC<GridItemProps> = ({ item, onEdit }) => {
  const [filters, setFilters] = useState({
    ...(item?.genericMetrics?.meta?.defaultFilters || {}),
  });

  useEffect(() => {
    let meta;

    if (item?.genericMetrics?.meta) {
      meta = {
        ...item.genericMetrics.meta,
        defaultFilters: filters || {},
      };
    }

    const updatedItem = {
      ...item,
      genericMetrics: {
        ...item.genericMetrics,
        meta,
      },
    };

    onEdit(updatedItem as WidgetData);
  }, [filters]);

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

export default GenericMetricsGridItem;
