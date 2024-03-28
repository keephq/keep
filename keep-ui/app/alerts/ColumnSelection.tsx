import { FormEvent, Fragment, useRef } from "react";
import { Table } from "@tanstack/table-core";
import { Button } from "@tremor/react";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { VisibilityState, ColumnOrderState } from "@tanstack/react-table";
import { FloatingArrow, arrow, offset, useFloating } from "@floating-ui/react";
import { Popover } from "@headlessui/react";
import { FiSettings } from "react-icons/fi";
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

  const [, setColumnVisibility] = useLocalStorage<VisibilityState>(
    `column-visibility-${presetName}`,
    DEFAULT_COLS_VISIBILITY
  );

  const [columnOrder, setColumnOrder] = useLocalStorage<ColumnOrderState>(
    `column-order-${presetName}`,
    DEFAULT_COLS
  );

  const columnsOptions = tableColumns
    .filter((col) => col.getIsPinned() === false)
    .map((col) => col.id);

  const selectedColumns = tableColumns
    .filter((col) => col.getIsVisible() && col.getIsPinned() === false)
    .map((col) => col.id);

  const onMultiSelectChange = (
    event: FormEvent<HTMLFormElement>,
    closePopover: VoidFunction
  ) => {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const valueKeys = Object.keys(Object.fromEntries(formData.entries()));

    const newColumnVisibility = columnsOptions.reduce<VisibilityState>(
      (acc, key) => {
        if (valueKeys.includes(key)) {
          return { ...acc, [key]: true };
        }

        return { ...acc, [key]: false };
      },
      {}
    );

    const originalColsOrder = columnOrder.filter((columnId) =>
      valueKeys.includes(columnId)
    );
    const newlyAddedCols = valueKeys.filter(
      (columnId) => !columnOrder.includes(columnId)
    );

    const newColumnOrder = [...originalColsOrder, ...newlyAddedCols];

    setColumnVisibility(newColumnVisibility);
    setColumnOrder(newColumnOrder);
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
            <ul className="space-y-2 mt-3 max-h-96 overflow-auto">
              {columnsOptions.map((column) => (
                <li key={column} className="space-x-2">
                  <input
                    name={column}
                    type="checkbox"
                    defaultChecked={selectedColumns.includes(column)}
                  />
                  <span>{column}</span>
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
