import {
    Button,
    Badge,
    Table as TremorTable,
    TableBody,
    TableCell,
    TableHead,
    TableHeaderCell,
    TableRow,
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
    onPaginationChange: ({ limit, offset }: { limit: number, offset: number }) => void;
    onRowClick?: (row: T) => void;
}

export function GenericTable<T>({
    data,
    columns,
    rowCount,
    offset,
    limit,
    onPaginationChange,
    onRowClick,
}: GenericTableProps<T>) {
    const [expanded, setExpanded] = useState<ExpandedState>({});
    const [pagination, setPagination] = useState({
        pageIndex: Math.ceil(offset / limit),
        pageSize: limit,
    });

    useEffect(() => {
        if (limit !== pagination.pageSize) {
            onPaginationChange({
                limit: pagination.pageSize,
                offset: 0,
            });
        }
        const currentOffset = pagination.pageSize * pagination.pageIndex;
        if (offset !== currentOffset) {
            onPaginationChange({
                limit: pagination.pageSize,
                offset: currentOffset,
            });
        }
    }, [pagination]);

    const table = useReactTable({
        columns,
        data,
        state: { expanded, pagination },
        getCoreRowModel: getCoreRowModel(),
        manualPagination: true,
        rowCount,
        onPaginationChange: setPagination,
        onExpandedChange: setExpanded,
    });

    return (
        <div className="flex flex-col w-full h-full max-h-full">
            <div className="overflow-auto h-1/2">
                <TremorTable className="w-full">
                    <TableHead>
                        {table.getHeaderGroups().map((headerGroup) => (
                            <TableRow
                                className="border-b border-tremor-border dark:border-dark-tremor-border"
                                key={headerGroup.id}
                            >
                                {headerGroup.headers.map((header) => (
                                    <TableHeaderCell
                                        className="text-tremor-content-strong dark:text-dark-tremor-content-strong"
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
                    <TableBody>
                        {table.getRowModel().rows.map((row) => (
                            <TableRow
                                className="even:bg-tremor-background-muted even:dark:bg-dark-tremor-background-muted hover:bg-slate-100 cursor-pointer"
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
            </div>
            <div className="mt-4">
                <Pagination table={table} isRefreshAllowed={true} />
            </div>
        </div>
    );
}
