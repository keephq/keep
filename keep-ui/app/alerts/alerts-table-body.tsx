import { TableBody, TableRow, TableCell } from "@tremor/react";
import { AlertDto } from "./models";
import "./alerts-table-body.css";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { Table, flexRender } from "@tanstack/react-table";

interface Props {
  table: Table<AlertDto>;
  showSkeleton?: boolean;
}

export function AlertsTableBody({ table, showSkeleton = true }: Props) {
  return (
    <TableBody>
      {table.getRowModel().rows.map((row) => (
        <TableRow key={row.id}>
          {row.getVisibleCells().map((cell) => (
            <TableCell key={cell.id}>
              {flexRender(cell.column.columnDef.cell, cell.getContext())}
            </TableCell>
          ))}
        </TableRow>
      ))}

      {showSkeleton && (
        <TableRow>
          <TableCell>
            <Skeleton />
          </TableCell>
          <TableCell>
            <Skeleton />
          </TableCell>
          <TableCell>
            <Skeleton />
          </TableCell>
          <TableCell>
            <Skeleton />
          </TableCell>
          <TableCell>
            <Skeleton />
          </TableCell>
          <TableCell>
            <Skeleton />
          </TableCell>
          <TableCell>
            <Skeleton />
          </TableCell>
          <TableCell>
            <Skeleton />
          </TableCell>
          <TableCell>
            <Skeleton />
          </TableCell>
        </TableRow>
      )}
    </TableBody>
  );
}
