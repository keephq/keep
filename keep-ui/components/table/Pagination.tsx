import {
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  TableCellsIcon,
} from "@heroicons/react/24/outline";
import { Button, Text } from "@tremor/react";
import { SingleValueProps, components, GroupBase } from "react-select";
import { Table } from "@tanstack/react-table";
import { Select } from "@/shared/ui";

interface Props<T> {
  table: Table<T>;
  isRefreshAllowed: boolean;
}

interface OptionType {
  value: string;
  label: string;
}

const SingleValue = ({
  children,
  ...props
}: SingleValueProps<OptionType, false, GroupBase<OptionType>>) => (
  <components.SingleValue {...props}>
    {children}
    <TableCellsIcon className="w-4 h-4 ml-2" />
  </components.SingleValue>
);

export default function Pagination<T>({ table, isRefreshAllowed }: Props<T>) {
  const pageIndex = table.getState().pagination.pageIndex;
  const pageCount = table.getPageCount();

  return (
    <div className="flex justify-end gap-4 items-center">
      <div className="flex gap-2 items-center">
        <Text className="font-bold">Rows per page</Text>
        <Select
          components={{ SingleValue }}
          value={{
            value: table.getState().pagination.pageSize.toString(),
            label: table.getState().pagination.pageSize.toString(),
          }}
          onChange={(selectedOption) =>
            table.setPageSize(Number(selectedOption!.value))
          }
          options={[
            { value: "10", label: "10" },
            { value: "25", label: "25" },
            { value: "50", label: "50" },
            { value: "100", label: "100" },
          ]}
          menuPlacement="top"
          className="rounded-md"
        />
      </div>
      <Text className="font-bold">
        Page {pageCount === 0 ? 0 : pageIndex + 1} of {pageCount}
      </Text>
      <div className="flex gap-2">
        <Button
          icon={ChevronDoubleLeftIcon}
          onClick={() => table.setPageIndex(0)}
          disabled={!table.getCanPreviousPage()}
          size="md"
          className="text-black border-gray-400 px-2"
          variant="secondary"
        />
        <Button
          icon={ChevronLeftIcon}
          onClick={table.previousPage}
          disabled={!table.getCanPreviousPage()}
          size="md"
          className="text-black border-gray-400 px-2"
          variant="secondary"
        />
        <Button
          icon={ChevronRightIcon}
          onClick={table.nextPage}
          disabled={!table.getCanNextPage()}
          size="md"
          className="text-black border-gray-400 px-2"
          variant="secondary"
        />
        <Button
          icon={ChevronDoubleRightIcon}
          onClick={() => table.setPageIndex(pageCount - 1)}
          disabled={!table.getCanNextPage()}
          size="md"
          className="text-black border-gray-400 px-2"
          variant="secondary"
        />
      </div>
    </div>
  );
}
