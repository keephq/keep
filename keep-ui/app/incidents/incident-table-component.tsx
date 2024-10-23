import {
  Icon,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import {
  Column,
  flexRender,
  Header,
  Table as ReactTable,
} from "@tanstack/react-table";
import React, { CSSProperties, ReactNode } from "react";
import { IncidentDto } from "./models";
import { useRouter } from "next/navigation";
import { FaArrowDown, FaArrowRight, FaArrowUp } from "react-icons/fa";
import clsx from "clsx";

// Styles to make sticky column pinning work!
const getCommonPinningStylesAndClassNames = (
  column: Column<any>
): { style: CSSProperties; className: string } => {
  const isPinned = column.getIsPinned();
  const isLastLeftPinnedColumn =
    isPinned === "left" && column.getIsLastColumn("left");
  const isFirstRightPinnedColumn =
    isPinned === "right" && column.getIsFirstColumn("right");

  return {
    style: {
      left: isPinned === "left" ? `${column.getStart("left")}px` : undefined,
      right: isPinned === "right" ? `${column.getAfter("right")}px` : undefined,
      width: column.getSize(),
      animationTimeline: "scroll(inline)",
    },
    className: clsx(
      "bg-tremor-background",
      column.getIsPinned() === false && "hover:bg-slate-100",
      isPinned ? "sticky" : "relative",
      isLastLeftPinnedColumn
        ? "animate-scroll-shadow-left"
        : isFirstRightPinnedColumn
          ? "animate-scroll-shadow-right"
          : undefined,
      isPinned ? "z-[1]" : "z-0"
    ),
  };
};

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

  const router = useRouter();

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
              className="even:bg-tremor-background-muted even:dark:bg-dark-tremor-background-muted hover:bg-slate-100 cursor-pointer"
              onClick={() => {
                router.push(`/incidents/${row.original.id}`);
              }}
            >
              {row.getVisibleCells().map((cell) => (
                <TableCell
                  key={cell.id}
                  {...getCommonPinningStylesAndClassNames(cell.column)}
                >
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
