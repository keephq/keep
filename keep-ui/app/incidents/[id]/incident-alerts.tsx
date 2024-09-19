import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import {
  Callout,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import Image from "next/image";
import AlertSeverity from "app/alerts/alert-severity";
import { AlertDto } from "app/alerts/models";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { getAlertLastReceieved } from "utils/helpers";
import {
  useIncidentAlerts,
  usePollIncidentAlerts,
} from "utils/hooks/useIncidents";
import AlertName from "app/alerts/alert-name";
import { ExclamationTriangleIcon } from "@radix-ui/react-icons";
import IncidentAlertMenu from "./incident-alert-menu";
import IncidentPagination from "../incident-pagination";
import React, { useEffect, useState } from "react";
import { IncidentDto } from "../models";

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

  const { data: alerts, isLoading } = useIncidentAlerts(
    incident.id,
    alertsPagination.limit,
    alertsPagination.offset
  );

  const [pagination, setTablePagination] = useState({
    pageIndex: alerts ? Math.ceil(alerts.offset / alerts.limit) : 0,
    pageSize: alerts ? alerts.limit : 20,
  });

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
  }, [pagination]);
  usePollIncidentAlerts(incident.id);

  const columns = [
    columnHelper.accessor("severity", {
      id: "severity",
      header: "Severity",
      minSize: 100,
      cell: (context) => <AlertSeverity severity={context.getValue()} />,
    }),
    columnHelper.display({
      id: "name",
      header: "Name",
      minSize: 330,
      cell: (context) => <AlertName alert={context.row.original} />,
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
  ];

  const table = useReactTable({
    columns: columns,
    manualPagination: true,
    state: { pagination },
    rowCount: alerts ? alerts.count : 0,
    onPaginationChange: setTablePagination,
    data: alerts?.items ?? [],
    getCoreRowModel: getCoreRowModel(),
  });
  return (
    <>
      {!isLoading && (alerts?.items ?? []).length === 0 && (
        <Callout
          className="mt-4 w-full"
          title="Missing Alerts"
          icon={ExclamationTriangleIcon}
          color={"orange"}
        >
          Alerts will show up here as they are correlated into this incident.
        </Callout>
      )}

      <Table>
        <TableHead>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header, index) => {
                return (
                  <TableHeaderCell key={`header-${header.id}-${index}`}>
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
                {row.getVisibleCells().map((cell, index) => (
                  <TableCell key={`cell-${cell.id}-${index}`}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
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

      <div className="mt-4 mb-8">
        <IncidentPagination table={table} isRefreshAllowed={true} />
      </div>
    </>
  );
}
