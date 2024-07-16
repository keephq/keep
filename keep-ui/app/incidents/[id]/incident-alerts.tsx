import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import {
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

interface Props {
  incidentFingerprint: string;
}

const columnHelper = createColumnHelper<AlertDto>();

export default function IncidentAlerts({ incidentFingerprint }: Props) {
  const { data: alerts } = useIncidentAlerts(incidentFingerprint);
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
        <span title={context.getValue().toISOString()}>
          {getAlertLastReceieved(context.getValue())}
        </span>
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
  ];
  const table = useReactTable({
    columns: columns,
    data: alerts ?? [],
    getCoreRowModel: getCoreRowModel(),
  });
  return (
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
            <TableRow key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <TableCell>
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
                <TableRow id={index}>
                  {columns.map((c) => (
                    <TableCell id={c.id}>
                      <Skeleton />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
          </TableBody>
        )
      }
    </Table>
  );
}
