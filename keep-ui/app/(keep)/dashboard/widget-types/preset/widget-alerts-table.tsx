import React, { useMemo } from "react";
import { WidgetData, WidgetType } from "../../types";
import { usePresetAlertsCount } from "@/features/presets/custom-preset-links";
import { useDashboardPreset } from "@/utils/hooks/useDashboardPresets";
import { Button, Icon } from "@tremor/react";
import { FireIcon } from "@heroicons/react/24/outline";
import { DynamicImageProviderIcon } from "@/components/ui";
import { getStatusColor, getStatusIcon } from "@/shared/lib/status-utils";
import { SeverityBorderIcon, UISeverity } from "@/shared/ui";
import { severityMapping } from "@/entities/alerts/model";
import * as Tooltip from "@radix-ui/react-tooltip";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { useRouter } from "next/navigation";
import TimeAgo from "react-timeago";
import { useSearchParams } from "next/navigation";

interface WidgetAlertsTableProps {
  alerts: any[];
  columns?: string[];
}

const WidgetAlertsTable: React.FC<WidgetAlertsTableProps> = ({
  alerts,
  columns,
}) => {
  const columnsMeta: { [key: string]: any } = {
    severity: {
      renderHeader: () => <div className="min-w-1"></div>,
      renderValue: (alert: any) => {
        <SeverityBorderIcon
          severity={
            (severityMapping[Number(alert.severity)] ||
              alert.severity) as UISeverity
          }
        />;
      },
    },
    status: {
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
    providerType: {
      renderHeader: () => <div className="min-w-4"></div>,
      renderValue: (alert: any) => (
        <DynamicImageProviderIcon
          className="inline-block"
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
      renderValue: (alert: any) => (
        <div className="max-w-32 truncate">{alert.name}</div>
      ),
    },
    description: {
      renderValue: (alert: any) => (
        <div className="max-w-32 truncate">{alert.description}</div>
      ),
    },
    lastReceived: {
      renderValue: (alert: any) => <TimeAgo date={alert.lastReceived} />,
    },
  };

  function renderHeaders() {
    return columns?.map((column) => {
      const columnMeta = columnsMeta[column];
      let columnHeaderValue;
      if (columnMeta?.renderHeader) {
        columnHeaderValue = columnMeta.renderHeader();
      } else {
        columnHeaderValue = <div className="max-w-full truncate">{column}</div>;
      }

      return (
        <th>
          <div className="flex items-center whitespace-nowrap">
            {columnHeaderValue}
          </div>
        </th>
      );
    });
  }

  function renderColumns(alert: any) {
    return columns?.map((column) => {
      const columnMeta = columnsMeta[column];
      let columnValue;
      if (columnMeta?.renderValue) {
        columnValue = columnMeta.renderValue(alert);
      } else {
        columnValue = <div className="max-w-32 truncate">{alert[column]}</div>;
      }

      return (
        <td>
          <div className="flex items-center">{columnValue}</div>
        </td>
      );
    });
  }

  return (
    <div className="widget-alerts-table">
      <table>
        <thead>
          <tr>{renderHeaders()}</tr>
        </thead>
        <tbody>
          {alerts?.map((alert) => (
            <tr key={alert.id}>{renderColumns(alert)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default WidgetAlertsTable;
