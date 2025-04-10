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
      renderValue: (alert: any) => alert.name,
    },
    description: {
      renderValue: (alert: any) => alert.description,
    },
  };

  function renderHeaders() {
    return columns?.map((column) => <th>{column}</th>);
  }

  function renderColumns(alert: any) {
    return columns?.map((column) => {
      const columnMeta = columnsMeta[column];
      let columnValue;
      if (columnMeta) {
        columnValue = columnMeta.renderValue(alert);
      } else {
        columnValue = <span>{alert[column]}</span>;
      }

      return <td>{columnValue}</td>;
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
