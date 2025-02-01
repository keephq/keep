"use client";

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import type { RowSelectionState } from "@tanstack/react-table";
import {
  Card,
  Icon,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import Image from "next/image";
import { AlertDto } from "@/entities/alerts/model";
import {
  useIncidentAlerts,
  usePollIncidentAlerts,
} from "utils/hooks/useIncidents";
import { AlertName } from "@/entities/alerts/ui";
import IncidentAlertMenu from "./incident-alert-menu";
import React, { useEffect, useMemo, useState } from "react";
import type { IncidentDto } from "@/entities/incidents/model";
import { getCommonPinningStylesAndClassNames, UISeverity } from "@/shared/ui";
import { EmptyStateCard } from "@/components/ui";
import { useRouter } from "next/navigation";
import {
  TableIndeterminateCheckbox,
  TablePagination,
  TableSeverityCell,
} from "@/shared/ui";
import { getStatusIcon, getStatusColor } from "@/shared/lib/status-utils";
import TimeAgo from "react-timeago";
import clsx from "clsx";
import { IncidentAlertsTableBodySkeleton } from "./incident-alert-table-body-skeleton";
import { IncidentAlertsActions } from "./incident-alert-actions";
import { DynamicImageProviderIcon } from "@/components/ui";
import { useRef, useCallback } from "react";
import { AlertNameWithDescription } from "@/entities/alerts/ui";
interface Props {
  incident: IncidentDto;
}

interface Pagination {
  limit: number;
  offset: number;
}

function useOptimalTableRows(
  containerRef: RefObject<HTMLElement>,
  {
    minRows = 2,
    maxRows = 20,
    rowHeight = 110,
    uiElementsHeight = 236 /* Height of UI elements: header (40px) + pagination (48px) + margins/padding (108px) */,
  } = {}
) {
  const [availableHeight, setAvailableHeight] = useState(0);
  const initialHeightSet = useRef(false);

  useEffect(() => {
    if (!containerRef.current || initialHeightSet.current) return;

    let resizeObserver: ResizeObserver; // Declare here so we can use in cleanup

    // Function to calculate and update height - only once
    const updateHeight = () => {
      if (initialHeightSet.current) return;

      const rect = containerRef.current?.getBoundingClientRect();
      if (rect && rect.height > 0) {
        setAvailableHeight(rect.height);
        initialHeightSet.current = true;

        // Cleanup listeners once we have our height
        if (resizeObserver) {
          resizeObserver.disconnect();
        }
        window.removeEventListener("resize", updateHeight);
      }
    };

    // Initial calculation
    updateHeight();

    // Create resize observer for initial size detection
    resizeObserver = new ResizeObserver(updateHeight);
    resizeObserver.observe(containerRef.current);

    // Add window resize listener for initial zoom state
    window.addEventListener("resize", updateHeight);

    // Cleanup
    return () => {
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      window.removeEventListener("resize", updateHeight);
    };
  }, []);

  return useMemo(() => {
    const tableHeight = availableHeight - uiElementsHeight;
    const optimalRows = Math.max(minRows, Math.floor(tableHeight / rowHeight));
    return Math.min(optimalRows, maxRows);
  }, [availableHeight, minRows, maxRows, rowHeight, uiElementsHeight]);
}

const columnHelper = createColumnHelper<AlertDto>();

export default function IncidentAlerts({ incident }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const optimalPageSize = useOptimalTableRows(containerRef);

  const [alertsPagination, setAlertsPagination] = useState<Pagination>({
    limit: optimalPageSize,
    offset: 0,
  });

  // Keep pagination in sync with optimal page size
  const [pagination, setTablePagination] = useState({
    pageIndex: 0,
    pageSize: optimalPageSize,
  });

  useEffect(() => {
    setTablePagination((prev) => ({
      pageIndex: 0,
      pageSize: optimalPageSize,
    }));

    setAlertsPagination((prev) => ({
      limit: optimalPageSize,
      offset: 0,
    }));
  }, [optimalPageSize]);

  useEffect(() => {
    if (pagination.pageSize !== alertsPagination.limit) {
      setAlertsPagination({
        limit: pagination.pageSize,
        offset: pagination.pageIndex * pagination.pageSize,
      });
    }
  }, [pagination]);

  const {
    data: alerts,
    isLoading: _alertsLoading,
    error: alertsError,
  } = useIncidentAlerts(
    incident.id,
    alertsPagination.limit,
    alertsPagination.offset
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

  const columns = useMemo(
    () => [
      columnHelper.display({
        id: "severity",
        header: () => <></>,
        cell: (context) => (
          <TableSeverityCell
            severity={context.row.original.severity as unknown as UISeverity}
          />
        ),
        size: 4,
        minSize: 4,
        maxSize: 4,
        meta: {
          tdClassName: "p-0",
          thClassName: "p-0",
        },
      }),
      columnHelper.display({
        id: "selected",
        minSize: 32,
        maxSize: 32,
        header: (context) => (
          <TableIndeterminateCheckbox
            checked={context.table.getIsAllRowsSelected()}
            indeterminate={context.table.getIsSomeRowsSelected()}
            onChange={context.table.getToggleAllRowsSelectedHandler()}
          />
        ),
        cell: (context) => (
          <TableIndeterminateCheckbox
            checked={context.row.getIsSelected()}
            indeterminate={context.row.getIsSomeSelected()}
            onChange={context.row.getToggleSelectedHandler()}
          />
        ),
      }),
      columnHelper.display({
        id: "name",
        header: "Name",
        minSize: 100,
        cell: (context) => (
          <div className="max-w-[300px]">
            <AlertNameWithDescription alert={context.row.original} />
          </div>
        ),
      }),
      columnHelper.accessor("status", {
        id: "status",
        minSize: 100,
        header: "Status",
        cell: (context) => (
          <span className="flex items-center gap-1 capitalize">
            <Icon
              icon={getStatusIcon(context.getValue())}
              size="sm"
              color={getStatusColor(context.getValue())}
              className="!p-0"
            />
            {context.getValue()}
          </span>
        ),
      }),
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
      columnHelper.accessor("lastReceived", {
        id: "lastReceived",
        header: "Last Event Time",
        minSize: 100,
        // data is a ISO string
        cell: (context) => <TimeAgo date={context.getValue()} />,
      }),
      columnHelper.accessor("source", {
        id: "source",
        header: "Source",
        maxSize: 100,
        cell: (context) =>
          (context.getValue() ?? []).map((source, index) => (
            <DynamicImageProviderIcon
              className={`inline-block ${index == 0 ? "" : "-ml-2"}`}
              key={`source-${source}-${index}`}
              alt={source}
              height={24}
              width={24}
              title={source}
              src={`/icons/${source}-icon.png`}
            />
          )),
      }),
      columnHelper.display({
        id: "remove",
        header: "Correlation",
        maxSize: 110,
        cell: (context) =>
          incident.is_confirmed && (
            <IncidentAlertMenu
              alert={context.row.original}
              incidentId={incident.id}
            />
          ),
      }),
    ],
    [incident.id, incident.is_confirmed]
  );

  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

  const table = useReactTable({
    data: alerts?.items ?? [],
    columns: columns,
    rowCount: alerts?.count ?? 0,
    getRowId: (row) => row.fingerprint,
    onRowSelectionChange: setRowSelection,
    state: {
      rowSelection,
      pagination,
      columnPinning: {
        left: ["severity", "selected", "name"],
        right: ["remove"],
      },
    },
    onPaginationChange: setTablePagination,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
  });

  const router = useRouter();

  if (!isLoading && (alerts?.items ?? []).length === 0) {
    return (
      <EmptyStateCard
        title="No alerts yet"
        description="Alerts will show up here as they are correlated into this incident."
        buttonText="Associate alerts manually"
        onClick={() => {
          router.push(`/alerts/feed`);
        }}
      />
    );
  }

  const selectedFingerprints = Object.keys(rowSelection);

  return (
    <div className="flex flex-col h-full" ref={containerRef}>
      <div className="flex justify-between items-center mb-2.5">
        <h2 className="text-tremor-default font-medium text-tremor-content-subtle dark:text-dark-tremor-content-subtle">
          ALERTS
        </h2>
        <IncidentAlertsActions
          incidentId={incident.id}
          selectedFingerprints={selectedFingerprints}
          resetAlertsSelection={() => table.resetRowSelection()}
        />
      </div>

      {/* Table container with flex-1 and overflow handling */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <div className="h-full overflow-auto">
          <Table>
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
              <TableBody>
                {table.getRowModel().rows.map((row, index) => (
                  <TableRow key={`row-${row.id}-${index}`}>
                    {row.getVisibleCells().map((cell, index) => {
                      const { style, className } =
                        getCommonPinningStylesAndClassNames(
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
                          {flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext()
                          )}
                        </TableCell>
                      );
                    })}
                  </TableRow>
                ))}
              </TableBody>
            )}
            {isLoading && (
              <IncidentAlertsTableBodySkeleton
                table={table}
                pageSize={optimalPageSize}
              />
            )}
          </Table>
        </div>
      </div>

      {/* Pagination at the bottom */}
      <div className="mt-4">
        <TablePagination table={table} pageSizeEnabled={false} />
      </div>
    </div>
  );
}
