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
import { useRouter } from "next/navigation";
import { FaArrowDown, FaArrowRight, FaArrowUp } from "react-icons/fa";
interface Props {
  table: ReactTable<IncidentDto>;
}

interface SortableHeaderCellProps {
  header: Header<IncidentDto, unknown>;
  children: ReactNode;
}

const SortableHeaderCell = ({ header, children }: SortableHeaderCellProps) => {
  const { column } = header;

  return (
    <TableHeaderCell
      // className="text-tremor-content-strong dark:text-dark-tremor-content-strong"
      className={`relative ${
        column.getIsPinned() === false ? "hover:bg-slate-100" : ""
      } group`}
    >
      <div className="flex items-center">
        {column.getCanSort() && (
          <>
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
            {/* Custom styled vertical line separator */}
            <div className="w-px h-5 mx-2 bg-gray-400"></div>
          </>
        )}
        {children} {/* Column name or text */}
      </div>
    </TableHeaderCell>
  );
};

export const IncidentTableComponent = (props: Props) => {
  const { table } = props;

  const router = useRouter();

  return (
    <Table className="mt-4">
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
              className="even:bg-tremor-background-muted even:dark:bg-dark-tremor-background-muted hover:bg-slate-100 cursor-pointer"
              key={row.id}
              onClick={() => {
                router.push(`/incidents/${row.original.id}`);
              }}
            >
              {row.getVisibleCells().map((cell) => (
                <TableCell key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          </>
        ))}
      </TableBody>
    </Table>
  );
};

export default IncidentTableComponent;
