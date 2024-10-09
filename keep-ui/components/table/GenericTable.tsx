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
    Table,
    ColumnDef,
} from "@tanstack/react-table";
import React, { HTMLProps, useEffect, useRef, useState } from "react";
import Pagination from "./Pagination";

interface GenericTableProps<T> {
    data: T[];
    columns: DisplayColumnDef<T>[];
    rowCount: number;
    offset: number;
    limit: number;
    onPaginationChange: ( limit: number, offset: number ) => void;
    onRowClick?: (row: T) => void;
    getActions?: (table: Table<T>, selectedRowIds: string[])=>React.JSX.Element;
    isRowSelectable?:boolean
}

interface Props extends HTMLProps<HTMLInputElement> {
    indeterminate?: boolean;
    disabled?: boolean;
  }

function TableCheckbox({
    indeterminate,
    className = "",
    disabled = false,
    ...rest
  }: Props) {
    const ref = useRef<HTMLInputElement>(null!);
  
    useEffect(() => {
      if (typeof indeterminate === "boolean") {
        ref.current.indeterminate = !rest.checked && indeterminate;
      }
    }, [indeterminate, rest.checked]);
  
    return (
      <input
        type="checkbox"
        ref={ref}
        disabled={disabled}
        className={
          className + `${disabled ? "cursor-not-allowed" : "cursor-pointer"}`
        }
        {...rest}
      />
    );
  }
  

export function GenericTable<T>({
    data,
    columns,
    rowCount,
    offset,
    limit,
    onPaginationChange,
    onRowClick,
    getActions,
    isRowSelectable = false,
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
            onPaginationChange(
                pagination.pageSize,
                currentOffset
            );
        }
    }, [pagination]);

    if(isRowSelectable && !!data.length) {
        columns = [{
            id: 'select-col',
            header: ({ table }) => (
           
            <TableCheckbox
                    checked={table.getIsAllRowsSelected()}
                    indeterminate={table.getIsSomeRowsSelected()}
                    onChange={table.getToggleAllRowsSelectedHandler()}
                  />
            ),
            cell: ({ row }) => (
              <TableCheckbox
                checked={row.getIsSelected()}
                disabled={!row.getCanSelect()}
                onChange={row.getToggleSelectedHandler()}
              />
            ),
          }, ...columns]
    }
    const table = useReactTable({
        columns,
        data,
        state: { expanded, pagination },
        getCoreRowModel: getCoreRowModel(),
        manualPagination: true,
        pageCount: Math.ceil(rowCount / limit), // Pass the total pages to React Table
        onPaginationChange: (updater) => {
            const nextPagination = typeof updater === "function" ? updater(pagination) : updater;
            setPagination(nextPagination);
        },
        onExpandedChange: setExpanded,
        enableRowSelection: !!data.length && true,
        enableMultiRowSelection: true,
    });

    const selectedRowIds = Object.entries(
        table.getSelectedRowModel().rowsById
      ).reduce<string[]>((acc, [id]) => {
        return acc.concat(id);
      }, []);

    return (
        <div className="flex flex-col w-full h-full max-h-full">
            <div className="overflow-auto h-1/2">
            {!!selectedRowIds.length  && getActions && <div className="mb-2">{getActions(table, selectedRowIds)}</div>}
                <TremorTable className="w-full rounded border border-tremor-border dark:border-dark-tremor-border">
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
            </div>
            <div className="mt-4">
                {pagination&&<Pagination
                    table={table}
                    isRefreshAllowed={false}
                />}
            </div>
        </div>
    );
}
