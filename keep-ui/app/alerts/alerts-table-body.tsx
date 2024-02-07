import { TableBody, TableRow, TableCell } from "@tremor/react";
import { AlertDto } from "./models";
import "./alerts-table-body.css";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { Table, flexRender } from "@tanstack/react-table";

interface Props {
  table: Table<AlertDto>;
  showSkeleton: boolean;
}

export function AlertsTableBody({ table, showSkeleton }: Props) {
  return (
    <TableBody>
      {table.getRowModel().rows.map((row) => (
        <TableRow key={row.id}>
          {row.getVisibleCells().map((cell) => (
            <TableCell
              key={cell.id}
              className={`bg-white ${
                cell.column.columnDef.meta?.tdClassName
                  ? cell.column.columnDef.meta?.tdClassName
                  : ""
              }`}
            >
              {flexRender(cell.column.columnDef.cell, cell.getContext())}
            </TableCell>
          ))}
        </TableRow>
      ))}
      {showSkeleton && (
        <TableRow>
          {table
            .getAllColumns()
            .filter((col) => col.getIsVisible())
            .map((col) => (
              <TableCell key={col.id}>
                <Skeleton />
              </TableCell>
            ))}
        </TableRow>
      )}
    </TableBody>
  );
}
