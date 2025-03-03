import { FormEvent, Fragment, useRef, useState } from "react";
import { Button, TextInput } from "@tremor/react";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { FloatingArrow, arrow, offset, useFloating } from "@floating-ui/react";
import { Popover } from "@headlessui/react";
import { FiSearch } from "react-icons/fi";
import { AlertDto } from "@/entities/alerts/model";
import { SquaresPlusIcon } from "@heroicons/react/24/outline";

interface AlertSidebarPopoverProps {
  alert: AlertDto | null;
}

export const ALERT_SIDEBAR_DEFAULT_COLS: string[] = [
  "description",
  "fingerprint",
];

export default function AlertSidebarPopover({
  alert,
}: AlertSidebarPopoverProps) {
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

  const getNestedKeys = (obj: Record<string, any>, prefix = ""): string[] => {
    let keys: string[] = [];

    for (const key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        const newKey = prefix ? `${prefix}.${key}` : key;
        if (["source", "name", "severity"].includes(newKey)) {
          continue;
        }
        if (Array.isArray(obj[key])) {
          keys.push(newKey);
        } else if (typeof obj[key] === "object" && obj[key] !== null) {
          keys = keys.concat(getNestedKeys(obj[key], newKey));
        } else {
          keys.push(newKey);
        }
      }
    }

    return keys;
  };

  const tableColumns = getNestedKeys(alert ?? {}, "");

  const [columnOrder, setColumnOrder] = useLocalStorage<string[]>(
    `alert-sidebar-visible-${alert?.fingerprint}`,
    ALERT_SIDEBAR_DEFAULT_COLS
  );

  const [searchTerm, setSearchTerm] = useState("");

  const filteredColumns = tableColumns.filter((column) =>
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

    // Create a new order array with all existing columns and newly selected columns
    const updatedOrder = [
      ...columnOrder,
      ...selectedColumnIds.filter((id) => !columnOrder.includes(id)),
    ];

    // Remove any columns that are no longer selected
    const finalOrder = updatedOrder.filter(
      (id) => selectedColumnIds.includes(id) || !filteredColumns.includes(id)
    );

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
            icon={SquaresPlusIcon}
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
                      defaultChecked={columnOrder.includes(column)}
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
