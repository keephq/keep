import { TableBody, TableRow, TableCell, Card, Callout } from "@tremor/react";
import { AlertDto } from "./models";
import "./alerts-table-body.css";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { Table, flexRender } from "@tanstack/react-table";
import { CircleStackIcon } from "@heroicons/react/24/outline";

interface Props {
  table: Table<AlertDto>;
  showSkeleton: boolean;
  showEmptyState: boolean;
  theme: { [key: string]: string };
  onRowClick: (alert: AlertDto) => void;
}

export function AlertsTableBody({
  table,
  showSkeleton,
  showEmptyState,
  theme,
  onRowClick,
}: Props) {
  if (showEmptyState) {
    return (
      <TableBody>
        <TableRow>
          <TableCell colSpan={table.getAllColumns().length} className="p-0">
            <div className="flex flex-col justify-center items-center h-96 w-full">
              <Card className="sm:mx-auto w-full max-w-5xl">
                <div className="text-center">
                  <CircleStackIcon
                    className="mx-auto h-7 w-7 text-tremor-content-subtle dark:text-dark-tremor-content-subtle"
                    aria-hidden={true}
                  />
                  <p className="mt-4 text-tremor-default font-medium text-tremor-content-strong dark:text-dark-tremor-content-strong">
                    No alerts to display
                  </p>
                  <p className="text-tremor-default text-tremor-content dark:text-dark-tremor-content">
                    It is because you have not connected any data source yet or
                    there are no alerts matching the filter.
                  </p>
                </div>
              </Card>
            </div>
          </TableCell>
        </TableRow>
      </TableBody>
    );
  }



  const handleRowClick = (e: React.MouseEvent, alert: AlertDto) => {
    // Prevent row click when clicking on specified elements
    if ((e.target as HTMLElement).closest("button, .menu, input, a, span, .prevent-row-click")) {
      return;
    }

    const rowElement = (e.currentTarget as HTMLElement);
    if (rowElement.classList.contains("menu-open")) {
      return;
    }

    onRowClick(alert);
  };

  return (
    <TableBody>
      {table.getRowModel().rows.map((row) => {
        // Assuming the severity can be accessed like this, adjust if needed
        const severity = row.original.severity || "info";
        const rowBgColor = theme[severity] || "bg-white"; // Fallback to 'bg-white' if no theme color

        return (
          <TableRow id={`alert-row-${row.original.fingerprint}`} key={row.id}
           className={`${rowBgColor} hover:bg-orange-100 cursor-pointer`}
           onClick={(e) => handleRowClick(e, row.original)}>
            {row.getVisibleCells().map((cell) => (
              <TableCell
                key={cell.id}
                className={
                  cell.column.columnDef.meta?.tdClassName
                    ? cell.column.columnDef.meta?.tdClassName
                    : ""
                }
              >
                {showSkeleton ? (
                  <Skeleton />
                ) : (
                  flexRender(cell.column.columnDef.cell, cell.getContext())
                )}
              </TableCell>
            ))}
          </TableRow>
        );
      })}
    </TableBody>
  );
}
