import { ArrowPathIcon, TableCellsIcon } from "@heroicons/react/24/outline";
import { ArrowLeftIcon, ArrowRightIcon } from "@radix-ui/react-icons";
import { Button, Select, SelectItem, Text } from "@tremor/react";
import { useState } from "react";
import { AlertDto } from "./models";
import { Table } from "@tanstack/react-table";
import { KeyedMutator } from "swr";

interface Props {
  table: Table<AlertDto>;
  mutate?: KeyedMutator<AlertDto[]>;
}

export default function AlertPagination({ table, mutate }: Props) {
  const [reloadLoading, setReloadLoading] = useState<boolean>(false);

  return (
    <div className="flex justify-between items-center">
      <Text>
        Showing {table.getState().pagination.pageIndex + 1} of{" "}
        {table.getPageCount()}
      </Text>
      <div className="flex">
        <Select
          value={table.getState().pagination.pageSize.toString()}
          enableClear={false}
          onValueChange={(newValue) => table.setPageSize(Number(newValue))}
          className="mr-2"
          icon={TableCellsIcon}
        >
          <SelectItem value="10">10</SelectItem>
          <SelectItem value="20">20</SelectItem>
          <SelectItem value="50">50</SelectItem>
          <SelectItem value="100">100</SelectItem>
        </Select>
        <Button
          icon={ArrowLeftIcon}
          onClick={() => table.previousPage()}
          disabled={!table.getCanPreviousPage()}
          size="xs"
          color="orange"
          variant="secondary"
          className="mr-1"
        />
        <Button
          icon={ArrowRightIcon}
          onClick={() => table.nextPage()}
          disabled={!table.getCanNextPage()}
          size="xs"
          color="orange"
          variant="secondary"
        />
        {mutate && (
          <Button
            icon={ArrowPathIcon}
            color="orange"
            size="xs"
            className="ml-2.5"
            disabled={reloadLoading}
            loading={reloadLoading}
            onClick={async () => {
              setReloadLoading(true);
              await mutate();
              setReloadLoading(false);
            }}
            title="Refresh"
          />
        )}
      </div>
    </div>
  );
}
