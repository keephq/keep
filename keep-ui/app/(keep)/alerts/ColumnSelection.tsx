import { FormEvent, Fragment, useRef, useState } from "react";
import { Table } from "@tanstack/table-core";
import { Button, TextInput } from "@tremor/react";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { VisibilityState, ColumnOrderState } from "@tanstack/react-table";
import { FloatingArrow, arrow, offset, useFloating } from "@floating-ui/react";
import { Popover } from "@headlessui/react";
import { FiSettings, FiSearch } from "react-icons/fi";
import { DEFAULT_COLS, DEFAULT_COLS_VISIBILITY } from "./alert-table-utils";
import { AlertDto } from "./models";

interface AlertColumnsSelectProps {
  table: Table<AlertDto>;
  presetName: string;
}

export default function ColumnSelection({
  table,
  presetName,
}: AlertColumnsSelectProps) {
  const arrowRef = useRef(null);
  const { refs, floatingStyles, context } = useFloating({
    strategy: "fixed",
    placement: "bottom-end",
    middleware: [
      offset({ mainAxis: 10 }),
      arrow({
        element: arrowRef,
      }),
    ],
  });
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

  const onMultiSelectChange = (
    event: FormEvent<HTMLFormElement>,
    closePopover: VoidFunction
  ) => {
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
    closePopover();
  };

  return (
    <Popover as={Fragment}>
      {({ close }) => (
        <>
          <Popover.Button
            variant="light"
            color="gray"
            as={Button}
            icon={FiSettings}
            ref={refs.setReference}
          />
          <Popover.Overlay className="fixed inset-0 bg-black opacity-30 z-20" />
          <Popover.Panel
            as="form"
            className="bg-white z-30 p-4 rounded-sm"
            ref={refs.setFloating}
            style={floatingStyles}
            onSubmit={(e) => onMultiSelectChange(e, close)}
          >
            <FloatingArrow
              className="fill-white [&>path:last-of-type]:stroke-white"
              ref={arrowRef}
              context={context}
            />
            <span className="text-gray-400 text-sm">Set table fields</span>
            <TextInput
              icon={FiSearch}
              placeholder="Search fields..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="mt-2"
            />
            <ul className="space-y-1 mt-3 max-h-96 overflow-auto">
              {filteredColumns.map((column) => (
                <li key={column}>
                  <label className="cursor-pointer p-2">
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
            <Button className="mt-5" color="orange" type="submit">
              Save changes
            </Button>
          </Popover.Panel>
        </>
      )}
    </Popover>
  );
}
