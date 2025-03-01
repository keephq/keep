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
import { Select } from "@/shared/ui";
import { useEffect, useMemo, useState } from "react";

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

interface Props {
  totalCount: number;
  pageSizeOptions?: number[];
  isRefreshAllowed: boolean;
  isRefreshing: boolean;
  onStateChange: (pageIndex: number, pageSize: number, offset: number) => void;
  onRefresh: () => void;
}

export function Pagination({
  totalCount,
  pageSizeOptions,
  isRefreshAllowed,
  isRefreshing,
  onStateChange,
  onRefresh,
}: Props) {
  const pageSizeOptionsMemoized = useMemo(
    () => pageSizeOptions || [20, 50, 100],
    [pageSizeOptions]
  );
  const selectOptions = useMemo(
    () =>
      pageSizeOptionsMemoized.map((value) => ({
        value: value.toString(),
        label: value.toString(),
      })),
    [pageSizeOptionsMemoized]
  );

  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(pageSizeOptionsMemoized[0]);
  const pagesCount = useMemo(
    () => Math.ceil(totalCount / pageSize),
    [totalCount, pageSize]
  );
  useEffect(
    () => onStateChange(pageIndex, pageSize, pageIndex * pageSize),
    [pageIndex, pageSize, onStateChange]
  );

  return (
    <div className="flex justify-between items-center">
      <Text>
        Showing {pagesCount === 0 ? 0 : pageIndex + 1} of {pagesCount}
      </Text>
      <div className="flex gap-1">
        <Select
          components={{ SingleValue }}
          value={{
            value: pageSize.toString(),
            label: pageSize.toString(),
          }}
          onChange={(selectedOption) =>
            setPageSize(Number(selectedOption!.value))
          }
          options={selectOptions}
          menuPlacement="top"
        />
        <div className="flex">
          <Button
            className="pagination-button"
            icon={ChevronDoubleLeftIcon}
            onClick={() => setPageIndex(0)}
            disabled={pageIndex == 0}
            size="xs"
            color="gray"
            variant="secondary"
          />
          <Button
            className="pagination-button"
            icon={ChevronLeftIcon}
            onClick={() => setPageIndex(pageIndex - 1)}
            disabled={pageIndex == 0}
            size="xs"
            color="gray"
            variant="secondary"
          />
          <Button
            className="pagination-button"
            icon={ChevronRightIcon}
            onClick={() => setPageIndex(pageIndex + 1)}
            disabled={pageIndex == pagesCount - 1}
            size="xs"
            color="gray"
            variant="secondary"
          />
          <Button
            className="pagination-button"
            icon={ChevronDoubleRightIcon}
            onClick={() => setPageIndex(pagesCount - 1)}
            disabled={pageIndex == pagesCount - 1}
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
