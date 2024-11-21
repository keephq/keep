import { TableBody, TableRow, TableCell, Card, Button } from "@tremor/react";
import { AlertDto } from "./models";
import "./alerts-table-body.css";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { Table, flexRender } from "@tanstack/react-table";
import React, { useState } from "react";
import PushAlertToServerModal from "./alert-push-alert-to-server-modal";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import clsx from "clsx";
import { getCommonPinningStylesAndClassNames } from "@/components/ui/table/utils";

interface Props {
  table: Table<AlertDto>;
  showSkeleton: boolean;
  showEmptyState: boolean;
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
}: Props) {
  const [modalOpen, setModalOpen] = useState(false);

  const handleModalClose = () => setModalOpen(false);
  const handleModalOpen = () => setModalOpen(true);

  if (showEmptyState) {
    return (
      <>
        <div className="flex flex-col justify-center items-center h-96 w-full absolute p-4">
          <EmptyStateCard
            title="No alerts to display"
            description="It is because you have not connected any data source yet or there are no alerts matching the filter."
            buttonText="Add Alert"
            onClick={handleModalOpen}
          />
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
                  key={clsx(
                    `cell-${c.id}-${cellIndex}`,
                    c.columnDef.meta?.tdClassName
                  )}
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
            className={clsx(
              "hover:bg-orange-100 cursor-pointer relative",
              rowBgColor
            )}
            onClick={(e) => handleRowClick(e, row.original)}
          >
            {row.getVisibleCells().map((cell) => {
              // TODO: fix multiple pinned columns
              // const { style, className } = getCommonPinningStylesAndClassNames(
              //   cell.column
              // );
              return (
                <TableCell
                  key={cell.id}
                  className={clsx(
                    cell.column.columnDef.meta?.tdClassName || "",
                    "relative z-[1]" // Ensure cell content is above the border
                  )}
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
