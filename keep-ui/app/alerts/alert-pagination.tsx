import { ArrowPathIcon, TableCellsIcon } from "@heroicons/react/24/outline";
import { ArrowLeftIcon, ArrowRightIcon } from "@radix-ui/react-icons";
import { Button, Select, SelectItem, Text } from "@tremor/react";
import { AlertDto } from "./models";
import { Table } from "@tanstack/react-table";
import { useAlerts } from "utils/hooks/useAlerts";

interface Props {
  table: Table<AlertDto>;
}

export default function AlertPagination({ table }: Props) {
  const { useAllAlerts } = useAlerts();
  const { mutate, isValidating } = useAllAlerts();

  const pageIndex = table.getState().pagination.pageIndex;
  const pageCount = table.getPageCount();

  return (
    <div className="flex justify-between items-center">
      <Text>
        Showing {pageCount === 0 ? 0 : pageIndex + 1} of {pageCount}
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
          onClick={table.previousPage}
          disabled={!table.getCanPreviousPage()}
          size="xs"
          color="orange"
          variant="secondary"
          className="mr-1"
        />
        <Button
          icon={ArrowRightIcon}
          onClick={table.nextPage}
          disabled={!table.getCanNextPage()}
          size="xs"
          color="orange"
          variant="secondary"
        />

        <Button
          icon={ArrowPathIcon}
          color="orange"
          size="xs"
          className="ml-2.5"
          disabled={isValidating}
          loading={isValidating}
          onClick={async () => await mutate()}
          title="Refresh"
        />
      </div>
    </div>
  );
}
