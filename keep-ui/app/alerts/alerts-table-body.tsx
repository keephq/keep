import { TableBody, TableRow, TableCell } from "@tremor/react";
import { AlertDto } from "./models";
import { Table, flexRender } from "@tanstack/react-table";
import "./alerts-table-body.css";

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
              className={`${
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
                <span className="block w-full h-2 bg-gray-200 rounded animate-pulse" />
              </TableCell>
            ))}
        </TableRow>
      )}
    </TableBody>
  );
}
