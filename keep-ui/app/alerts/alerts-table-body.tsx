import { TableBody, TableRow, TableCell } from "@tremor/react";
import { AlertDto } from "./models";
import "./alerts-table-body.css";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { Table, flexRender } from "@tanstack/react-table";

interface Props {
  table: Table<AlertDto>;
  showSkeleton: boolean;
  theme: { [key: string]: string };
}


export function AlertsTableBody({ table, showSkeleton, theme }: Props) {
  return (
    <TableBody>
      {table.getRowModel().rows.map((row) => {
        // Assuming the severity can be accessed like this, adjust if needed
        const severity = row.original.severity || "info";
        const rowBgColor = theme[severity] || 'bg-white'; // Fallback to 'bg-white' if no theme color

        return (
          <TableRow key={row.id} className={rowBgColor}>
            {row.getVisibleCells().map((cell) => (
              <TableCell
                key={cell.id}
                className={
                  cell.column.columnDef.meta?.tdClassName
                    ? cell.column.columnDef.meta?.tdClassName
                    : ""
                }
              >
                {showSkeleton
                  ? <Skeleton />
                  : flexRender(cell.column.columnDef.cell, cell.getContext())
                }
              </TableCell>
            ))}
          </TableRow>
        );
      })}
    </TableBody>
  );
}
