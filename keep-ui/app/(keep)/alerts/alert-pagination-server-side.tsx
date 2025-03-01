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
import { Select } from "@/shared/ui";
import { useEffect } from "react";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { RowStyle } from "./RowStyleSelection";

interface Props {
  table: Table<AlertDto>;
  isRefreshAllowed: boolean;
  isRefreshing: boolean;
  onRefresh: () => void;
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

export default function AlertPaginationServerSide({
  table,
  isRefreshAllowed,
  isRefreshing,
  onRefresh,
}: Props) {
  const pageIndex = table.getState().pagination.pageIndex;
  const pageCount = table.getPageCount();
  const [rowStyle] = useLocalStorage<RowStyle>(
    "alert-table-row-style",
    "default"
  );

  // Track if the user has manually changed the page size
  const [userPageSizePreference, setUserPageSizePreference] =
    useLocalStorage<boolean>("alert-table-user-page-size-set", false);

  // Keep track of previous row style to detect changes
  const [previousRowStyle, setPreviousRowStyle] =
    useLocalStorage<RowStyle | null>("alert-table-previous-row-style", null);

  // Listen for changes in rowStyle and adjust the page size accordingly
  useEffect(() => {
    // Skip adjustment if user has set their own preference
    if (userPageSizePreference) return;

    const currentPageSize = table.getState().pagination.pageSize;

    // If this is the first time setting the row style, just record it and exit
    if (!previousRowStyle) {
      setPreviousRowStyle(rowStyle);
      return;
    }

    // If switching from default to dense, and current page size is the default (20)
    if (
      rowStyle === "dense" &&
      previousRowStyle === "default" &&
      currentPageSize === 20
    ) {
      table.setPageSize(50);
    }
    // If switching from dense to default, and current page size is 50 (the dense default)
    else if (
      rowStyle === "default" &&
      previousRowStyle === "dense" &&
      currentPageSize === 50
    ) {
      table.setPageSize(20);
    }

    // Update the previous row style
    setPreviousRowStyle(rowStyle);
  }, [
    rowStyle,
    previousRowStyle,
    table,
    userPageSizePreference,
    setPreviousRowStyle,
  ]);

  // Handler for when user manually changes page size
  const handlePageSizeChange = (selectedOption: OptionType | null) => {
    if (!selectedOption) return;

    const newSize = Number(selectedOption.value);
    table.setPageSize(newSize);

    // Record that user has set their own preference
    setUserPageSizePreference(true);
  };

  return (
    <div className="flex justify-between items-center">
      <Text>
        Showing {pageCount === 0 ? 0 : pageIndex + 1} of {pageCount}
      </Text>
      <div className="flex gap-1">
        <Select
          components={{ SingleValue }}
          value={{
            value: table.getState().pagination.pageSize.toString(),
            label: table.getState().pagination.pageSize.toString(),
          }}
          onChange={handlePageSizeChange}
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
            disabled={isRefreshing}
            loading={isRefreshing}
            onClick={async () => onRefresh()}
            title="Refresh"
          />
        )}
      </div>
    </div>
  );
}
