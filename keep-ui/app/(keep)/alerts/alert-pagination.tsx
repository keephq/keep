import {
  ArrowPathIcon,
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  TableCellsIcon,
} from "@heroicons/react/16/solid";
import { Button, Text } from "@tremor/react";
import { SingleValueProps, components, GroupBase } from "react-select";
import { AlertDto } from "@/entities/alerts/model";
import { Table } from "@tanstack/react-table";
import { useAlerts } from "utils/hooks/useAlerts";
import { Select } from "@/shared/ui";

interface Props {
  presetName: string;
  table: Table<AlertDto>;
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

export default function AlertPagination({
  presetName,
  table,
  isRefreshAllowed,
}: Props) {
  const { usePresetAlerts } = useAlerts();
  const { mutate, isLoading: isValidating } = usePresetAlerts(presetName);

  const pageIndex = table.getState().pagination.pageIndex;
  const pageCount = table.getPageCount();

  return (
    <div className="flex justify-between items-center">
      <Text>
        {pageCount ? (
          <>
            Showing {pageCount === 0 ? 0 : pageIndex + 1} of {pageCount}
          </>
        ) : null}
      </Text>
      <div className="flex gap-1">
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
            { value: "20", label: "20" },
            { value: "50", label: "50" },
            { value: "100", label: "100" },
          ]}
          menuPlacement="top"
        />
        <div className="flex">
          <Button
            className="pagination-button"
            icon={ChevronDoubleLeftIcon}
            onClick={() => table.setPageIndex(0)}
            disabled={!table.getCanPreviousPage()}
            size="xs"
            color="gray"
            variant="secondary"
          />
          <Button
            className="pagination-button"
            icon={ChevronLeftIcon}
            onClick={table.previousPage}
            disabled={!table.getCanPreviousPage()}
            size="xs"
            color="gray"
            variant="secondary"
          />
          <Button
            className="pagination-button"
            icon={ChevronRightIcon}
            onClick={table.nextPage}
            disabled={!table.getCanNextPage()}
            size="xs"
            color="gray"
            variant="secondary"
          />
          <Button
            className="pagination-button"
            icon={ChevronDoubleRightIcon}
            onClick={() => table.setPageIndex(pageCount - 1)}
            disabled={!table.getCanNextPage()}
            size="xs"
            color="gray"
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
