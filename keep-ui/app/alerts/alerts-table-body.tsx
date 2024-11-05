import { TableBody, TableRow, TableCell, Card, Button } from "@tremor/react";
import { AlertDto } from "./models";
import "./alerts-table-body.css";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { Table, flexRender } from "@tanstack/react-table";
import React, { useState } from "react";
import PushAlertToServerModal from "./alert-push-alert-to-server-modal";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { getSeverityBorderStyle } from "@/utils/getSeverityBorderStyle";
import classnames from "classnames";

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
        <div className="flex flex-col justify-center items-center h-96 w-full absolute top-1/3">
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

  return (
    <TableBody>
      {table.getRowModel().rows.map((row) => {
        // Assuming the severity can be accessed like this, adjust if needed
        const severity = row.original.severity || "info";
        const rowBgColor = theme[severity] || "bg-white"; // Fallback to 'bg-white' if no theme color
        const severityBorderClass = getSeverityBorderStyle(
          row.original.severity
        );

        return (
          <TableRow
            id={`alert-row-${row.original.fingerprint}`}
            key={row.id}
            className={`${rowBgColor} ${severityBorderClass} hover:bg-orange-100 cursor-pointer`}
            onClick={(e) => handleRowClick(e, row.original)}
          >
            {row.getVisibleCells().map((cell) => (
              <TableCell
                key={cell.id}
                className={classnames(
                  cell.column.columnDef.meta?.tdClassName || "",
                  "relative z-10" // Ensure cell content is above the border
                )}
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
