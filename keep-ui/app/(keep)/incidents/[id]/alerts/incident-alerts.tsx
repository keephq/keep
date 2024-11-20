"use client";

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import {
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import Image from "next/image";
import AlertSeverity from "@/app/(keep)/alerts/alert-severity";
import { AlertDto } from "@/app/(keep)/alerts/models";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { getAlertLastReceieved } from "utils/helpers";
import {
  useIncidentAlerts,
  usePollIncidentAlerts,
} from "utils/hooks/useIncidents";
import AlertName from "@/app/(keep)/alerts/alert-name";
import IncidentAlertMenu from "./incident-alert-menu";
import React, { useEffect, useMemo, useState } from "react";
import type { IncidentDto } from "@/entities/incidents/model";
import { getCommonPinningStylesAndClassNames } from "@/components/ui/table/utils";
// import AlertTableCheckbox from "@/app/alerts/alert-table-checkbox";
import { EmptyStateCard } from "@/components/ui";
import { useRouter } from "next/navigation";
import { TablePagination } from "@/shared/ui";

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
  } = useIncidentAlerts(
    incident.id,
    alertsPagination.limit,
    alertsPagination.offset
  );

  // TODO: Load data on server side
  // Loading state is true if the data is not loaded and there is no error for smoother loading state on initial load
  const isLoading = _alertsLoading || (!alerts && !alertsError);

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
      // TODO: Add back when we have Split action
      // columnHelper.display({
      //   id: "selected",
      //   size: 10,
      //   header: (context) => (
      //     <AlertTableCheckbox
      //       checked={context.table.getIsAllRowsSelected()}
      //       indeterminate={context.table.getIsSomeRowsSelected()}
      //       onChange={context.table.getToggleAllRowsSelectedHandler()}
      //       onClick={(e) => e.stopPropagation()}
      //     />
      //   ),
      //   cell: (context) => (
      //     <AlertTableCheckbox
      //       checked={context.row.getIsSelected()}
      //       indeterminate={context.row.getIsSomeSelected()}
      //       onChange={context.row.getToggleSelectedHandler()}
      //       onClick={(e) => e.stopPropagation()}
      //     />
      //   ),
      // }),
      columnHelper.accessor("severity", {
        id: "severity",
        header: "Severity",
        minSize: 80,
        cell: (context) => (
          <div className="text-center">
            <AlertSeverity severity={context.getValue()} />
          </div>
        ),
      }),
      columnHelper.display({
        id: "name",
        header: "Name",
        minSize: 100,
        cell: (context) => (
          <div className="max-w-[300px]">
            <AlertName alert={context.row.original} />
          </div>
        ),
      }),
      columnHelper.accessor("description", {
        id: "description",
        header: "Description",
        minSize: 100,
        cell: (context) => (
          <div title={context.getValue()}>
            <div className="truncate">{context.getValue()}</div>
          </div>
        ),
      }),
      columnHelper.accessor("status", {
        id: "status",
        minSize: 100,
        header: "Status",
      }),
      columnHelper.accessor("is_created_by_ai", {
        id: "is_created_by_ai",
        header: "🔗",
        minSize: 50,
        cell: (context) => (
          <>
            {context.getValue() ? (
              <div title="Correlated with AI">🤖</div>
            ) : (
              <div title="Correlated manually">👨‍💻</div>
            )}
          </>
        ),
      }),
      columnHelper.accessor("lastReceived", {
        id: "lastReceived",
        header: "Last Received",
        minSize: 100,
        cell: (context) => (
          <span>{getAlertLastReceieved(context.getValue())}</span>
        ),
      }),
      columnHelper.accessor("source", {
        id: "source",
        header: "Source",
        minSize: 100,
        cell: (context) =>
          (context.getValue() ?? []).map((source, index) => (
            <Image
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
        header: "",
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

  const table = useReactTable({
    data: alerts?.items ?? [],
    columns: columns,
    rowCount: alerts?.count ?? 0,
    state: {
      pagination,
      columnPinning: {
        left: ["selected"],
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

  return (
    <>
      <Card className="p-0 overflow-hidden">
        <Table>
          <TableHead>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header, index) => {
                  const { style, className } =
                    getCommonPinningStylesAndClassNames(header.column);
                  return (
                    <TableHeaderCell
                      key={`header-${header.id}-${index}`}
                      style={style}
                      className={className}
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
                <TableRow
                  key={`row-${row.id}-${index}`}
                  className="hover:bg-slate-100"
                >
                  {row.getVisibleCells().map((cell, index) => {
                    const { style, className } =
                      getCommonPinningStylesAndClassNames(cell.column);
                    return (
                      <TableCell
                        key={`cell-${cell.id}-${index}`}
                        style={style}
                        className={className}
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
          {
            // Skeleton
            (isLoading || (alerts?.items ?? []).length === 0) && (
              <TableBody>
                {Array(pagination.pageSize)
                  .fill("")
                  .map((index, rowIndex) => (
                    <TableRow key={`row-${index}-${rowIndex}`}>
                      {columns.map((c, cellIndex) => (
                        <TableCell key={`cell-${c.id}-${cellIndex}`}>
                          <Skeleton />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
              </TableBody>
            )
          }
        </Table>
      </Card>

      <div className="mt-4 mb-8">
        <TablePagination table={table} />
      </div>
    </>
  );
}
