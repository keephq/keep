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
import { useIncidentAlerts } from "utils/hooks/useIncidents";
import AlertName from "app/alerts/alert-name";
import { ExclamationTriangleIcon } from "@radix-ui/react-icons";
import IncidentAlertMenu from "./incident-alert-menu";

interface Props {
  incidentId: string;
}

const columnHelper = createColumnHelper<AlertDto>();

export default function IncidentAlerts({ incidentId }: Props) {
  const { data: alerts } = useIncidentAlerts(incidentId);

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
            key={source}
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
      cell: (context) => (
        <IncidentAlertMenu
          alert={context.row.original}
          incidentId={incidentId}
        />
      ),
    }),
  ];

  const table = useReactTable({
    columns: columns,
    data: alerts ?? [],
    getCoreRowModel: getCoreRowModel(),
  });
  return (
    <>
      {(alerts ?? []).length === 0 && (
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
              {headerGroup.headers.map((header) => {
                return (
                  <TableHeaderCell key={header.id}>
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
        {alerts && alerts.length > 0 && (
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow key={row.id} className="hover:bg-slate-100">
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        )}
        {
          // Skeleton
          (alerts ?? []).length === 0 && (
            <TableBody>
              {Array(5)
                .fill("")
                .map((index) => (
                  <TableRow key={index}>
                    {columns.map((c) => (
                      <TableCell key={c.id}>
                        <Skeleton />
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
            </TableBody>
          )
        }
      </Table>
    </>
  );
}
