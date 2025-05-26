import React, { useEffect, useMemo } from "react";
import { WidgetData, WidgetType } from "../../types";
import { usePresetAlertsCount } from "@/features/presets/custom-preset-links";
import { useDashboardPreset } from "@/utils/hooks/useDashboardPresets";
import { Button, Icon } from "@tremor/react";
import { FireIcon } from "@heroicons/react/24/outline";
import { DynamicImageProviderIcon } from "@/components/ui";
import { getStatusColor, getStatusIcon } from "@/shared/lib/status-utils";
import { getNestedValue } from "@/shared/lib/object-utils";
import { SeverityBorderIcon, UISeverity } from "@/shared/ui";
import { severityMapping } from "@/entities/alerts/model";
import * as Tooltip from "@radix-ui/react-tooltip";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { useRouter } from "next/navigation";
import TimeAgo from "react-timeago";
import { useSearchParams } from "next/navigation";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { ColumnRenameMapping } from "@/widgets/alerts-table/ui/alert-table-column-rename";
import { DEFAULT_COLS } from "@/widgets/alerts-table/lib/alert-table-utils";
import { ColumnOrderState } from "@tanstack/table-core";
import { startCase } from "lodash";
import { defaultColumns } from "./constants";

interface WidgetAlertsTableProps {
  presetName: string;
  alerts?: any[];
  columns?: string[];
  background?: string;
}

const WidgetAlertsTable: React.FC<WidgetAlertsTableProps> = ({
  presetName,
  alerts,
  columns,
  background,
}) => {
  const columnsGapClass = "pr-3";
  const borderClass = "border-b";

  const [columnRenameMapping] = useLocalStorage<ColumnRenameMapping>(
    `column-rename-mapping-${presetName}`,
    {}
  );

  const [presetOrderedColumns] = useLocalStorage<ColumnOrderState>(
    `column-order-${presetName}`,
    DEFAULT_COLS
  );

  const columnsMeta: { [key: string]: any } = useMemo(
    () => ({
      severity: {
        gridColumnTemplate: "min-content",
        renderHeader: () => <div className="min-w-1"></div>,
        renderValue: (alert: any) => (
          <SeverityBorderIcon
            severity={
              (severityMapping[Number(alert.severity)] ||
                alert.severity) as UISeverity
            }
          />
        ),
      },
      status: {
        gridColumnTemplate: "min-content",
        renderHeader: () => <div className="min-w-4"></div>,
        renderValue: (alert: any) => (
          <Icon
            icon={getStatusIcon(alert.status)}
            size="sm"
            color={getStatusColor(alert.status)}
            className="!p-0"
          />
        ),
      },
      source: {
        gridColumnTemplate: "min-content",
        renderHeader: () => <div className="min-w-4"></div>,
        renderValue: (alert: any) => (
          <DynamicImageProviderIcon
            className="inline-block min-w-4 min-h-4"
            alt={(alert as any).providerType}
            height={16}
            width={16}
            title={(alert as any).providerType}
            providerType={(alert as any).providerType}
            src={`/icons/${(alert as any).providerType}-icon.png`}
          />
        ),
      },
      name: {
        gridColumnTemplate: "minmax(100px, 1fr)",
        renderValue: (alert: any) => (
          <div title={alert.name} className="truncate overflow-hidden text-ellipsis">
            {alert.name}
          </div>
        ),
      },
      description: {
        gridColumnTemplate: "minmax(100px, 1fr)",
        renderValue: (alert: any) => (
          <div title={alert.description} className="truncate overflow-hidden text-ellipsis">
            {alert.description}
          </div>
        ),
      },
      lastReceived: {
        gridColumnTemplate: "min-content",
        renderValue: (alert: any) => <TimeAgo date={alert.lastReceived} />,
      },
    }),
    [columnRenameMapping]
  );

  const orderedColumns = useMemo(() => {
    const presetColumns: string[] = columns || defaultColumns;
    const indexed: { [key: string]: number } = (
      presetOrderedColumns || defaultColumns
    ).reduce((prev, curr, index) => ({ ...prev, [curr]: index }), {});

    return presetColumns.slice().sort((firstColum, secondColumn) => {
      const indexOfFirst = indexed[firstColum] || 0;
      const indexOfSecond = indexed[secondColumn] || 0;
      return indexOfFirst - indexOfSecond;
    });
  }, [columns, presetOrderedColumns]);

  function renderHeaders() {
    return orderedColumns?.map((column, index) => {
      const columnMeta = columnsMeta[column];
      let columnHeaderValue;
      if (columnMeta?.renderHeader) {
        columnHeaderValue = columnMeta.renderHeader();
      } else {
        columnHeaderValue = (
          <div className="max-w-32 truncate">
            {columnRenameMapping[column] || startCase(column)}
          </div>
        );
      }

      return (
        <div
          key={column}
          className={`flex h-6 items-center whitespace-nowrap text-xs font-bold ${borderClass} ${index < orderedColumns.length - 1 ? columnsGapClass : ""}`}
        >
          {columnHeaderValue}
        </div>
      );
    });
  }

  function renderTableBody() {
    const alertsToRender = alerts || Array.from({ length: 5 }).fill(undefined);

    return alertsToRender
      ?.map((alert, alertIndex) => {
        return orderedColumns?.map((column, index) => {
          const columnMeta = columnsMeta[column];
          let columnValue;
          if (!alert) {
            columnValue = <Skeleton containerClassName="w-full" />;
          } else if (columnMeta?.renderValue) {
            columnValue = columnMeta.renderValue(alert);
          } else {
            columnValue = (
              <div className="truncate overflow-hidden text-ellipsis">{getNestedValue(alert, column)}</div>
            );
          }
          const _columnsGapClass =
            index < orderedColumns.length - 1 ? columnsGapClass : "";
          const _borderClass =
            alertIndex < alertsToRender.length - 1 ? borderClass : "";

          return (
            <div
              key={`${column}-${alertIndex}`}
              title={alert?.[column]}
              className={`min-h-7 text-xs flex min-w-0 items-center overflow-hidden whitespace-nowrap ${_borderClass} ${_columnsGapClass}`}
            >
              {columnValue}
            </div>
          );
        });
      })
      .flat();
  }

  const gridTemplateColumns = useMemo(
    () =>
      orderedColumns
        ?.map((column) => {
          const columnMeta = columnsMeta[column];
          let gridColumnTemplate = "auto";

          if (columnMeta?.gridColumnTemplate) {
            gridColumnTemplate = columnMeta.gridColumnTemplate;
          } else {
            // Default sizing for arbitrary columns
            gridColumnTemplate = "minmax(auto, 1fr)";
          }

          return gridColumnTemplate;
        })
        .join(" "),
    [orderedColumns, columnsMeta]
  );

  return (
    <div
      style={{ background }}
      className="bg-opacity-25 max-w-full overflow-x-auto border rounded-md"
    >
      <div
        style={{ gridTemplateColumns }}
        className="grid min-w-fit px-2"
      >
        {renderHeaders()}
        {renderTableBody()}
      </div>
    </div>
  );
};

export default WidgetAlertsTable;
