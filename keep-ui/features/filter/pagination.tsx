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
import { useMemo } from "react";

export interface PaginationState {
  limit: number;
  offset: number;
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

interface Props {
  totalCount: number;
  pageSizeOptions?: number[];
  isRefreshAllowed: boolean;
  isRefreshing: boolean;
  state: PaginationState;
  onStateChange: (paginationState: PaginationState) => void;
  onRefresh?: () => void;
}

export function Pagination({
  totalCount,
  pageSizeOptions,
  isRefreshAllowed,
  isRefreshing,
  state,
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

  const pagesCount = useMemo(
    () => Math.ceil(totalCount / state.limit),
    [totalCount, state]
  );
  const pageIndex = useMemo(() => {
    return Math.ceil(state.offset / state.limit);
  }, [state]);

  function setPageIndex(pageIndex: number): void {
    onStateChange({
      limit: state.limit,
      offset: pageIndex * state.limit,
    });
  }

  return (
    <div className="flex justify-between items-center">
      <Text>
        Showing {pagesCount === 0 ? 0 : pageIndex + 1} of {pagesCount}
      </Text>
      <div className="flex gap-1">
        <Select
          components={{ SingleValue }}
          value={{
            value: state.limit.toString(),
            label: state.limit.toString(),
          }}
          onChange={(selectedOption) =>
            onStateChange({ ...state, limit: Number(selectedOption!.value) })
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
            onClick={async () => onRefresh?.()}
            title="Refresh"
          />
        )}
      </div>
    </div>
  );
}
