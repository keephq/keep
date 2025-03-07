import { FormEvent, Fragment, useRef, useState } from "react";
import { Table } from "@tanstack/table-core";
import { Button, TextInput } from "@tremor/react";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { VisibilityState, ColumnOrderState } from "@tanstack/react-table";
import { FiSearch } from "react-icons/fi";
import { DEFAULT_COLS, DEFAULT_COLS_VISIBILITY } from "./alert-table-utils";
import { AlertDto } from "@/entities/alerts/model";

interface AlertColumnsSelectProps {
  table: Table<AlertDto>;
  presetName: string;
  onClose?: () => void;
}

export default function ColumnSelection({
  table,
  presetName,
  onClose,
}: AlertColumnsSelectProps) {
  const tableColumns = table.getAllColumns();

  const [columnVisibility, setColumnVisibility] =
    useLocalStorage<VisibilityState>(
      `column-visibility-${presetName}`,
      DEFAULT_COLS_VISIBILITY
    );

  const [columnOrder, setColumnOrder] = useLocalStorage<ColumnOrderState>(
    `column-order-${presetName}`,
    DEFAULT_COLS
  );

  const [searchTerm, setSearchTerm] = useState("");

  const columnsOptions = tableColumns
    .filter((col) => col.getIsPinned() === false)
    .map((col) => col.id);

  const selectedColumns = tableColumns
    .filter((col) => col.getIsVisible() && col.getIsPinned() === false)
    .map((col) => col.id);

  const filteredColumns = columnsOptions.filter((column) =>
    column.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const onMultiSelectChange = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const selectedColumnIds = Object.keys(
      Object.fromEntries(formData.entries())
    );

    // Update visibility only for the currently visible (filtered) columns.
    const newColumnVisibility = { ...columnVisibility };
    filteredColumns.forEach((column) => {
      newColumnVisibility[column] = selectedColumnIds.includes(column);
    });

    // Create a new order array with all existing columns and newly selected columns
    const updatedOrder = [
      ...columnOrder,
      ...selectedColumnIds.filter((id) => !columnOrder.includes(id)),
    ];

    // Remove any columns that are no longer selected
    const finalOrder = updatedOrder.filter(
      (id) => selectedColumnIds.includes(id) || !filteredColumns.includes(id)
    );

    setColumnVisibility(newColumnVisibility);
    setColumnOrder(finalOrder);
    onClose?.();
  };

  return (
    <form onSubmit={onMultiSelectChange} className="flex flex-col h-full">
      <div className="flex-1 overflow-hidden flex flex-col">
        <span className="text-gray-400 text-sm mb-2">Set table fields</span>
        <TextInput
          icon={FiSearch}
          placeholder="Search fields..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="mb-3"
        />
        <div className="flex-1 overflow-y-auto max-h-[350px]">
          <ul className="space-y-1">
            {filteredColumns.map((column) => (
              <li key={column}>
                <label className="cursor-pointer p-2 flex items-center">
                  <input
                    className="mr-2"
                    name={column}
                    type="checkbox"
                    defaultChecked={columnVisibility[column]}
                  />
                  {column}
                </label>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <Button className="mt-4" color="orange" type="submit">
        Save changes
      </Button>
    </form>
  );
}
