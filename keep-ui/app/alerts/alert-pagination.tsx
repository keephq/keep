import {
  ArrowPathIcon,
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  TableCellsIcon,
} from "@heroicons/react/24/outline";
import { Button, Select, SelectItem, Text } from "@tremor/react";
import { AlertDto } from "./models";
import { Table } from "@tanstack/react-table";
import { useAlerts } from "utils/hooks/useAlerts";

interface Props {
  table: Table<AlertDto>;
  isRefreshAllowed: boolean;
}

export default function AlertPagination({ table, isRefreshAllowed }: Props) {
  const { useAllAlerts } = useAlerts();
  const { mutate, isValidating } = useAllAlerts();

  const pageIndex = table.getState().pagination.pageIndex;
  const pageCount = table.getPageCount();

  return (
    <div className="flex justify-between items-center">
      <Text>
        Showing {pageCount === 0 ? 0 : pageIndex + 1} of {pageCount}
      </Text>
      <div className="flex gap-1">
        <Select
          value={table.getState().pagination.pageSize.toString()}
          enableClear={false}
          onValueChange={(newValue) => table.setPageSize(Number(newValue))}
          icon={TableCellsIcon}
        >
          <SelectItem value="10">10</SelectItem>
          <SelectItem value="20">20</SelectItem>
          <SelectItem value="50">50</SelectItem>
          <SelectItem value="100">100</SelectItem>
        </Select>
        <div className="flex">
          <Button
            icon={ChevronDoubleLeftIcon}
            onClick={() => table.setPageIndex(0)}
            disabled={!table.getCanPreviousPage()}
            size="xs"
            color="orange"
            variant="secondary"
          />
          <Button
            icon={ChevronLeftIcon}
            onClick={table.previousPage}
            disabled={!table.getCanPreviousPage()}
            size="xs"
            color="orange"
            variant="secondary"
          />
          <Button
            icon={ChevronRightIcon}
            onClick={table.nextPage}
            disabled={!table.getCanNextPage()}
            size="xs"
            color="orange"
            variant="secondary"
          />
          <Button
            icon={ChevronDoubleRightIcon}
            onClick={() => table.setPageIndex(pageCount - 1)}
            disabled={!table.getCanNextPage()}
            size="xs"
            color="orange"
            variant="secondary"
          />
        </div>
        {isRefreshAllowed && (
          <Button
            icon={ArrowPathIcon}
            color="orange"
            size="xs"
            disabled={isValidating}
            loading={isValidating}
            onClick={async () => await mutate()}
            title="Refresh"
          />
        )}
      </div>
    </div>
  );
}
