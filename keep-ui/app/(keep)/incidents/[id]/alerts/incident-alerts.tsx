"use client";

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import type { RowSelectionState } from "@tanstack/react-table";
import {
  Button,
  Card,
  Table,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import { AlertDto, severityMapping } from "@/entities/alerts/model";
import {
  useIncidentAlerts,
  usePollIncidentAlerts,
} from "utils/hooks/useIncidents";
import React, { useEffect, useState } from "react";
import { IncidentDto, useIncidentActions } from "@/entities/incidents/model";
import {
  EmptyStateCard,
  getCommonPinningStylesAndClassNames,
  UISeverity,
} from "@/shared/ui";
import { useRouter } from "next/navigation";
import {
  TablePagination,
  } from "@/shared/ui";
import clsx from "clsx";
import { IncidentAlertsTableBodySkeleton } from "./incident-alert-table-body-skeleton";
import { IncidentAlertsActions } from "./incident-alert-actions";
import { ViewAlertModal } from "@/app/(keep)/alerts/ViewAlertModal";
import { IncidentAlertActionTray } from "./incident-alert-action-tray";
import { BellAlertIcon } from "@heroicons/react/24/outline";
import { AlertsTableBody } from "@/app/(keep)/alerts/alerts-table-body";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import {
  useAlertTableCols,
} from "@/app/(keep)/alerts/alert-table-utils";
interface Props {
  incident: IncidentDto;
}

interface Pagination {
  limit: number;
  offset: number;
}

const columnHelper = createColumnHelper<AlertDto>();

export default function IncidentAlerts({ incident }: Props) {
  const [alertsPagination, setAlertsPagination] = useState<Pagination>({
    limit: 20,
    offset: 0,
  });

  const [pagination, setTablePagination] = useState({
    pageIndex: 0,
    pageSize: 20,
  });

  const {
    data: alerts,
    isLoading: _alertsLoading,
    error: alertsError,
    mutate: mutateAlerts,
  } = useIncidentAlerts(
    incident.id,
    alertsPagination.limit,
    alertsPagination.offset
  );
  const { unlinkAlertsFromIncident } = useIncidentActions();

  const [theme, setTheme] = useLocalStorage(
    "alert-table-theme",
    Object.values(severityMapping).reduce<{ [key: string]: string }>(
      (acc, severity) => {
        acc[severity] = "bg-white";
        return acc;
      },
      {}
    )
  );

  // TODO: Load data on server side
  // Loading state is true if the data is not loaded and there is no error for smoother loading state on initial load
  const isLoading = _alertsLoading || (!alerts && !alertsError);
  const isTopologyIncident = incident.incident_type === "topology";

  useEffect(() => {
    if (alerts && alerts.limit != pagination.pageSize) {
      setAlertsPagination({
        limit: pagination.pageSize,
        offset: 0,
      });
    }
    const currentOffset = pagination.pageSize * pagination.pageIndex;
    if (alerts && alerts.offset != currentOffset) {
      setAlertsPagination({
        limit: pagination.pageSize,
        offset: currentOffset,
      });
    }
  }, [alerts, pagination]);
  usePollIncidentAlerts(incident.id);

  // Add new state for the ViewAlertModal
  const [viewAlertModal, setViewAlertModal] = useState<AlertDto | null>(null);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

  const extraColumns = [
    columnHelper.accessor("is_created_by_ai", {
      id: "is_created_by_ai",
      header: "Correlation",
      minSize: 50,
      cell: (context) => {
        if (isTopologyIncident) {
          return <div title="Correlated with topology">🌐 Topology</div>;
        }
        return (
          <>
            {context.getValue() ? (
              <div title="Correlated with AI">🤖 AI</div>
            ) : (
              <div title="Correlated manually">👨‍💻 Manually</div>
            )}
          </>
        );
      },
    }),
  ];

  const MenuComponent = (alert: AlertDto) => {
    return (
      <div className="opacity-0 group-hover/row:opacity-100">
        <IncidentAlertActionTray
          alert={alert}
          onViewAlert={setViewAlertModal}
          onUnlink={async (alert) => {
            if (!incident.is_candidate) {
              await unlinkAlertsFromIncident(
                incident.id,
                [alert.fingerprint],
                mutateAlerts
              );
            }
          }}
          isCandidate={incident.is_candidate}
        />
      </div>
    );
  };

  const alertTableColumns = useAlertTableCols({
    isCheckboxDisplayed: true,
    isMenuDisplayed: true,
    presetName: "incident-alerts",
    presetNoisy: false,
    MenuComponent: MenuComponent,
    extraColumns: extraColumns,
  });

  const table = useReactTable({
    data: alerts?.items ?? [],
    columns: alertTableColumns,
    rowCount: alerts?.count ?? 0,
    getRowId: (row) => row.fingerprint,
    onRowSelectionChange: setRowSelection,
    state: {
      columnOrder: [
        "severity",
        "checkbox",
        "status",
        "source",
        "name",
        "description",
        "is_created_by_ai",
      ],
      columnVisibility: { extraPayload: false, assignee: false },
      columnPinning: {
        left: ["severity", "checkbox", "status", "source", "name"],
        right: ["alertMenu"],
      },
      rowSelection,
      pagination,
    },

    onPaginationChange: setTablePagination,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
  });

  const router = useRouter();

  if (!isLoading && (alerts?.items ?? []).length === 0) {
    return (
      <EmptyStateCard
        className="w-full"
        title="No alerts yet"
        description="Alerts will show up here as they are correlated into this incident."
        icon={BellAlertIcon}
      >
        <div className="flex gap-2">
          <Button
            color="orange"
            variant="secondary"
            size="md"
            onClick={() => {
              router.push(`/alerts/feed`);
            }}
          >
            Add Alerts Manually
          </Button>
          <Button
            color="orange"
            variant="primary"
            size="md"
            onClick={() => {
              router.push(`/alerts/feed?createIncidentsFromLastAlerts=50`);
            }}
          >
            Try AI Correlation
          </Button>
        </div>
      </EmptyStateCard>
    );
  }

  const selectedFingerprints = Object.keys(rowSelection);

  function renderRows() {
    // This trick handles cases when rows have duplicated ids
    // It shouldn't happen, but the API currently returns duplicated ids
    // And in order to mitigate this issue, we append the rowIndex to the key for duplicated keys
    const visitedIds = new Set<string>();

    return table.getRowModel().rows.map((row, rowIndex) => {
      let renderingKey = row.id;

      if (visitedIds.has(renderingKey)) {
        renderingKey = `${renderingKey}-${rowIndex}`;
      } else {
        visitedIds.add(renderingKey);
      }

      return (
        <TableRow
          key={`row-${row.id}-${rowIndex}`}
          className="group/row hover:bg-gray-50"
        >
          {row.getVisibleCells().map((cell, index) => {
            const { style, className } = getCommonPinningStylesAndClassNames(
              cell.column,
              table.getState().columnPinning.left?.length,
              table.getState().columnPinning.right?.length
            );
            return (
              <TableCell
                key={`cell-${cell.id}-${index}`}
                style={style}
                className={clsx(
                  cell.column.columnDef.meta?.tdClassName,
                  className
                )}
              >
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </TableCell>
            );
          })}
        </TableRow>
      );
    });
  }

  return (
    <>
      <IncidentAlertsActions
        incidentId={incident.id}
        selectedFingerprints={selectedFingerprints}
        resetAlertsSelection={() => table.resetRowSelection()}
      />
      <Card className="p-0 overflow-x-auto h-[calc(100vh-30rem)]">
        <Table className="[&>table]:table-fixed group">
          <TableHead>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow
                key={headerGroup.id}
                className="border-b border-tremor-border dark:border-dark-tremor-border"
              >
                {headerGroup.headers.map((header, index) => {
                  const { style, className } =
                    getCommonPinningStylesAndClassNames(
                      header.column,
                      table.getState().columnPinning.left?.length,
                      table.getState().columnPinning.right?.length
                    );
                  return (
                    <TableHeaderCell
                      key={`header-${header.id}-${index}`}
                      style={style}
                      className={clsx(
                        header.column.columnDef.meta?.thClassName,
                        className
                      )}
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                    </TableHeaderCell>
                  );
                })}
              </TableRow>
            ))}
          </TableHead>
          {alerts && alerts?.items?.length > 0 && (
            // <TableBody>{renderRows()}</TableBody>
            <AlertsTableBody
              table={table}
              showSkeleton={false}
              theme={theme}
              onRowClick={() => {}}
              lastViewedAlert={null}
              presetName={"incident-alerts"}
            />
          )}
          {isLoading && (
            <IncidentAlertsTableBodySkeleton
              table={table}
              pageSize={pagination.pageSize - 10}
            />
          )}
        </Table>
      </Card>

      <div className="mt-4 mb-8">
        <TablePagination table={table} />
      </div>

      <ViewAlertModal
        alert={viewAlertModal}
        handleClose={() => setViewAlertModal(null)}
        mutate={mutateAlerts}
      />
    </>
  );
}
