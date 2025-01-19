import {
  Table as TremorTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Card,
} from "@tremor/react";
import {
  DisplayColumnDef,
  ExpandedState,
  getCoreRowModel,
  useReactTable,
  flexRender,
} from "@tanstack/react-table";
import React, { useEffect, useState } from "react";
import Pagination from "./Pagination";

interface GenericTableProps<T> {
  data: T[];
  columns: DisplayColumnDef<T>[];
  rowCount: number;
  offset: number;
  limit: number;
  onPaginationChange: (limit: number, offset: number) => void;
  onRowClick?: (row: T) => void;
  dataFetchedAtOneGO?: boolean;
}

export function GenericTable<T>({
  data,
  columns,
  rowCount,
  offset,
  limit,
  onPaginationChange,
  onRowClick,
  dataFetchedAtOneGO,
}: GenericTableProps<T>) {
  const [expanded, setExpanded] = useState<ExpandedState>({});
  const [pagination, setPagination] = useState({
    pageIndex: Math.floor(offset / limit),
    pageSize: limit,
  });

  useEffect(() => {
    setPagination({
      pageIndex: Math.floor(offset / limit),
      pageSize: limit,
    });
  }, [offset, limit]);

  useEffect(() => {
    const currentOffset = pagination.pageSize * pagination.pageIndex;
    if (offset !== currentOffset || limit !== pagination.pageSize) {
      onPaginationChange(pagination.pageSize, currentOffset);
    }
  }, [pagination]);

  const finalData = (
    dataFetchedAtOneGO
      ? data.slice(
          pagination.pageSize * pagination.pageIndex,
          pagination.pageSize * (pagination.pageIndex + 1)
        )
      : data
  ) as T[];

  const table = useReactTable({
    columns,
    data: finalData,
    state: { expanded, pagination },
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: Math.ceil(rowCount / limit), // Pass the total pages to React Table
    onPaginationChange: (updater) => {
      const nextPagination =
        typeof updater === "function" ? updater(pagination) : updater;
      setPagination(nextPagination);
    },
    onExpandedChange: setExpanded,
  });

  return (
    <div className="flex flex-col gap-4 w-full h-full max-h-full">
      <Card className="p-0">
        <TremorTable className="w-full">
          <TableHead>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow
                className="border-b border-tremor-border dark:border-dark-tremor-border"
                key={headerGroup.id}
              >
                {headerGroup.headers.map((header) => (
                  <TableHeaderCell
                    className="text-gray-400 dark:text-dark-gray-400"
                    key={header.id}
                  >
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext()
                    )}
                  </TableHeaderCell>
                ))}
              </TableRow>
            ))}
          </TableHead>
          <TableBody className="bg-gray-20">
            {table.getRowModel().rows.map((row) => (
              <TableRow
                className=" hover:bg-slate-100 cursor-pointer"
                key={row.id}
                onClick={() => onRowClick?.(row.original)}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </TremorTable>
      </Card>
      {pagination && <Pagination table={table} isRefreshAllowed={false} />}
    </div>
  );
}
