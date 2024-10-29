import {
  Icon,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import { flexRender, Header, Table as ReactTable } from "@tanstack/react-table";
import React, { ReactNode } from "react";
import { IncidentDto } from "./models";
import { FaArrowDown, FaArrowRight, FaArrowUp } from "react-icons/fa";
import clsx from "clsx";
import { getCommonPinningStylesAndClassNames } from "@/components/ui/table/utils";

interface Props {
  table: ReactTable<IncidentDto>;
}

interface SortableHeaderCellProps {
  header: Header<IncidentDto, unknown>;
  children: ReactNode;
}

const SortableHeaderCell = ({ header, children }: SortableHeaderCellProps) => {
  const { column } = header;
  const { style, className } = getCommonPinningStylesAndClassNames(column);

  return (
    <TableHeaderCell
      className={clsx("relative bg-tremor-background group", className)}
      style={style}
    >
      <div className="flex items-center">
        {children} {/* Column name or text */}
        {column.getCanSort() && (
          <>
            {/* Custom styled vertical line separator */}
            <div className="w-px h-5 mx-2 bg-gray-400"></div>
            <Icon
              className="cursor-pointer"
              size="xs"
              color="neutral"
              onClick={(event) => {
                event.stopPropagation();
                const toggleSorting = header.column.getToggleSortingHandler();
                if (toggleSorting) toggleSorting(event);
              }}
              tooltip={
                column.getNextSortingOrder() === "asc"
                  ? "Sort ascending"
                  : column.getNextSortingOrder() === "desc"
                    ? "Sort descending"
                    : "Clear sort"
              }
              icon={
                column.getIsSorted()
                  ? column.getIsSorted() === "asc"
                    ? FaArrowDown
                    : FaArrowUp
                  : FaArrowRight
              }
            >
              {/* Icon logic */}
            </Icon>
          </>
        )}
      </div>
    </TableHeaderCell>
  );
};

export const IncidentTableComponent = (props: Props) => {
  const { table } = props;

  return (
    <Table>
      <TableHead>
        {table.getHeaderGroups().map((headerGroup) => (
          <TableRow
            className="border-b border-tremor-border dark:border-dark-tremor-border"
            key={headerGroup.id}
          >
            {headerGroup.headers.map((header) => {
              return (
                <SortableHeaderCell header={header} key={header.id}>
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext()
                  )}
                </SortableHeaderCell>
              );
            })}
          </TableRow>
        ))}
      </TableHead>
      <TableBody>
        {table.getRowModel().rows.map((row) => (
          <>
            <TableRow
              key={row.id}
              className="even:bg-tremor-background-muted even:dark:bg-dark-tremor-background-muted"
            >
              {row.getVisibleCells().map((cell) => {
                const { style, className } =
                  getCommonPinningStylesAndClassNames(cell.column);
                return (
                  <TableCell
                    key={cell.id}
                    style={style}
                    className={clsx(
                      className,
                      cell.column.id === "actions" ? "p-1" : ""
                    )}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                );
              })}
            </TableRow>
          </>
        ))}
      </TableBody>
    </Table>
  );
};

export default IncidentTableComponent;
