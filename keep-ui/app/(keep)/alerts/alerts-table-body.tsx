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
import { Row } from "@tanstack/react-table";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { GroupedRow } from "./alert-grouped-row";

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
      {table.getRowModel().rows.map((row) => (
        <GroupedRow
          key={row.id}
          row={row}
          table={table}
          theme={theme}
          onRowClick={onRowClick}
        />
      ))}
    </TableBody>
  );
}
