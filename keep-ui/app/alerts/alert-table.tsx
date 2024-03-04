import { Table, Callout } from "@tremor/react";
import { AlertsTableBody } from "./alerts-table-body";
import { AlertDto } from "./models";
import { CircleStackIcon } from "@heroicons/react/24/outline";
import {
  OnChangeFn,
  RowSelectionState,
  getCoreRowModel,
  useReactTable,
  getPaginationRowModel,
  ColumnDef,
  ColumnOrderState,
  VisibilityState,
  ColumnSizingState,
  getFilteredRowModel,
} from "@tanstack/react-table";
import { useTheme } from "next-themes";
import AlertPagination from "./alert-pagination";
import AlertColumnsSelect from "./alert-columns-select";
import AlertsTableHeaders from "./alert-table-headers";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import {
  getColumnsIds,
  getOnlyVisibleCols,
  DEFAULT_COLS_VISIBILITY,
  DEFAULT_COLS,
} from "./alert-table-utils";

interface Props {
  alerts: AlertDto[];
  columns: ColumnDef<AlertDto>[];
  isAsyncLoading?: boolean;
  presetName: string;
  isMenuColDisplayed?: boolean;
  isRefreshAllowed?: boolean;
  rowSelection?: {
    state: RowSelectionState;
    onChange: OnChangeFn<RowSelectionState>;
  };
}

export function AlertTable({
  alerts,
  columns,
  isAsyncLoading = false,
  presetName,
  rowSelection,
  isRefreshAllowed = true,
}: Props) {
  const { theme } = useTheme();

  const columnsIds = getColumnsIds(columns);

  const [columnOrder] = useLocalStorage<ColumnOrderState>(
    `column-order-${presetName}`,
    DEFAULT_COLS
  );

  const [columnVisibility] = useLocalStorage<VisibilityState>(
    `column-visibility-${presetName}`,
    DEFAULT_COLS_VISIBILITY
  );

  const [columnSizing, setColumnSizing] = useLocalStorage<ColumnSizingState>(
    "table-sizes",
    {}
  );

  const table = useReactTable({
    data: alerts,
    columns: columns,
    state: {
      columnVisibility: getOnlyVisibleCols(columnVisibility, columnsIds),
      columnOrder: columnOrder,
      columnSizing: columnSizing,
      rowSelection: rowSelection?.state,
      columnPinning: {
        left: ["checkbox"],
        right: ["alertMenu"],
      },
    },
    initialState: {
      pagination: { pageSize: 10 },
    },
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    enableRowSelection: rowSelection !== undefined,
    onRowSelectionChange: rowSelection?.onChange,
    onColumnSizingChange: setColumnSizing,
    enableColumnPinning: true,
    columnResizeMode: "onChange",
    autoResetPageIndex: false,
  });

  return (
    <>
      <AlertColumnsSelect presetName={presetName} table={table} />
      {isAsyncLoading && (
        <Callout
          title="Getting your alerts..."
          icon={CircleStackIcon}
          color={theme === "dark" ? "white" : "slate"}
          className="mt-5"
        >
          Alerts will show up in this table as they are added to Keep...
        </Callout>
      )}
      <Table className="[&>table]:table-fixed [&>table]:w-full">
        <AlertsTableHeaders
          columns={columns}
          table={table}
          presetName={presetName}
        />
        <AlertsTableBody table={table} showSkeleton={isAsyncLoading} />
      </Table>
      <AlertPagination table={table} isRefreshAllowed={isRefreshAllowed} />
    </>
  );
}
