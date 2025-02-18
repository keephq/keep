import { TableBody, TableRow, TableCell } from "@tremor/react";
import { AlertDto } from "@/entities/alerts/model";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { Table, flexRender } from "@tanstack/react-table";
import React, { useState } from "react";
import PushAlertToServerModal from "./alert-push-alert-to-server-modal";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import clsx from "clsx";
import { getCommonPinningStylesAndClassNames } from "@/shared/ui";

interface Props {
  table: Table<AlertDto>;
  showSkeleton: boolean;
  showEmptyState: boolean;
  showFilterEmptyState?: boolean;
  showSearchEmptyState?: boolean;
  theme: { [key: string]: string };
  onRowClick: (alert: AlertDto) => void;
  presetName: string;
}

export function AlertsTableBody({
  table,
  showSkeleton,
  showEmptyState,
  theme,
  onRowClick,
  presetName,
  showFilterEmptyState,
  showSearchEmptyState,
}: Props) {
  const [modalOpen, setModalOpen] = useState(false);

  const handleModalClose = () => setModalOpen(false);
  const handleModalOpen = () => setModalOpen(true);

  if (!showSkeleton) {
    if (
      table.getPageCount() === 0 &&
      !showFilterEmptyState &&
      !showSearchEmptyState
    ) {
      return (
        <>
          <div className="flex items-center h-full w-full absolute -mt-20">
            <div className="flex flex-col justify-center items-center w-full p-4">
              <EmptyStateCard
                title="No alerts to display"
                description="It is because you have not connected any data source yet or there are no alerts matching the filter."
                buttonText="Add Alert"
                onClick={handleModalOpen}
              />
            </div>
          </div>
          {modalOpen && (
            <PushAlertToServerModal
              handleClose={handleModalClose}
              presetName={presetName}
            />
          )}
        </>
      );
    }

    if (showFilterEmptyState) {
      return (
        <>
          <div className="flex items-center h-full w-full absolute -mt-20">
            <div className="flex flex-col justify-center items-center w-full p-4">
              <EmptyStateCard
                title="No alerts to display matching your filter"
                buttonText="Clear filter"
                onClick={() => console.log("")}
              />
            </div>
          </div>
        </>
      );
    }

    if (showSearchEmptyState) {
      return (
        <>
          <div className="flex items-center h-full w-full absolute -mt-20">
            <div className="flex flex-col justify-center items-center w-full p-4">
              <EmptyStateCard title="No alerts to display matching your CEL query" />
            </div>
          </div>
        </>
      );
    }
  }

  const handleRowClick = (e: React.MouseEvent, alert: AlertDto) => {
    // Prevent row click when clicking on specified elements
    if (
      (e.target as HTMLElement).closest(
        "button, .menu, input, a, span, .prevent-row-click"
      )
    ) {
      return;
    }

    const rowElement = e.currentTarget as HTMLElement;
    if (rowElement.classList.contains("menu-open")) {
      return;
    }

    onRowClick(alert);
  };

  if (showSkeleton) {
    return (
      <TableBody>
        {Array(20)
          .fill("")
          .map((index, rowIndex) => (
            <TableRow key={`row-${index}-${rowIndex}`}>
              {table.getAllColumns().map((c, cellIndex) => (
                <TableCell
                  key={`cell-${c.id}-${cellIndex}`}
                  className={c.columnDef.meta?.tdClassName}
                >
                  <Skeleton containerClassName="w-full" />
                </TableCell>
              ))}
            </TableRow>
          ))}
      </TableBody>
    );
  }

  return (
    <TableBody>
      {table.getRowModel().rows.map((row) => {
        // Assuming the severity can be accessed like this, adjust if needed
        const severity = row.original.severity || "info";
        const rowBgColor = theme[severity] || "bg-white"; // Fallback to 'bg-white' if no theme color
        return (
          <TableRow
            id={`alert-row-${row.original.fingerprint}`}
            key={row.id}
            className="cursor-pointer relative group"
            onClick={(e) => handleRowClick(e, row.original)}
          >
            {row.getVisibleCells().map((cell) => {
              const { style, className } = getCommonPinningStylesAndClassNames(
                cell.column,
                table.getState().columnPinning.left?.length,
                table.getState().columnPinning.right?.length
              );
              return (
                <TableCell
                  key={cell.id}
                  className={clsx(
                    cell.column.columnDef.meta?.tdClassName,
                    className,
                    rowBgColor,
                    "group-hover:bg-orange-100"
                  )}
                  style={style}
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              );
            })}
          </TableRow>
        );
      })}
    </TableBody>
  );
}
