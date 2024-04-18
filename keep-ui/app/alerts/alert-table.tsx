import { Table, Callout, Card, Icon } from "@tremor/react";
import { AlertsTableBody } from "./alerts-table-body";
import { AlertDto } from "./models";
import { CircleStackIcon } from "@heroicons/react/24/outline";
import {
  getCoreRowModel,
  useReactTable,
  getPaginationRowModel,
  ColumnDef,
  ColumnOrderState,
  VisibilityState,
  ColumnSizingState,
  getFilteredRowModel,
  SortingState,
  getSortedRowModel,
} from "@tanstack/react-table";

import AlertPagination from "./alert-pagination";
import AlertsTableHeaders from "./alert-table-headers";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import {
  getColumnsIds,
  getOnlyVisibleCols,
  DEFAULT_COLS_VISIBILITY,
  DEFAULT_COLS,
} from "./alert-table-utils";
import AlertActions from "./alert-actions";
import AlertPresets from "./alert-presets";
import { evalWithContext } from "./alerts-rules-builder";
import { TitleAndFilters } from "./TitleAndFilters";
import { severityMapping } from "./models";
import { useState } from "react";


interface Props {
  alerts: AlertDto[];
  columns: ColumnDef<AlertDto>[];
  isAsyncLoading?: boolean;
  presetName: string;
  presetPrivate?: boolean;
  presetNoisy?: boolean;
  isMenuColDisplayed?: boolean;
  isRefreshAllowed?: boolean;
}

export function AlertTable({
  alerts,
  columns,
  isAsyncLoading = false,
  presetName,
  presetPrivate = false,
  presetNoisy = false,
  isRefreshAllowed = true,
}: Props) {
  const [theme, setTheme] = useLocalStorage('alert-table-theme',
    Object.values(severityMapping).reduce<{ [key: string]: string }>((acc, severity) => {
      acc[severity] = 'bg-white';
      return acc;
    }, {})
  );


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

  const handleThemeChange = (newTheme: any) => {
    setTheme(newTheme);
  };

  const [sorting, setSorting] = useState<SortingState>([]);


  const table = useReactTable({
    data: alerts,
    columns: columns,
    state: {
      columnVisibility: getOnlyVisibleCols(columnVisibility, columnsIds),
      columnOrder: columnOrder,
      columnSizing: columnSizing,
      columnPinning: {
        left: presetNoisy ? ["noise", "checkbox"] : ["checkbox"],
        right: ["alertMenu"],
      },
      sorting: sorting,
    },
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    initialState: {
      pagination: { pageSize: 10 },
    },
    globalFilterFn: ({ original }, _id, value) => {
      return evalWithContext(original, value);
    },
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onColumnSizingChange: setColumnSizing,
    enableColumnPinning: true,
    columnResizeMode: "onChange",
    autoResetPageIndex: false,
    enableGlobalFilter: true,
    enableSorting: true,
  });

  const selectedRowIds = Object.entries(
    table.getSelectedRowModel().rowsById
  ).reduce<string[]>((acc, [alertId]) => {
    return acc.concat(alertId);
  }, []);

  return (
    <>
      <TitleAndFilters table={table} alerts={alerts} presetName={presetName}  onThemeChange={handleThemeChange}/>
      <Card className="mt-7 px-4 pb-4 md:pb-10 md:px-4 pt-6">
        {selectedRowIds.length ? (
          <AlertActions
            selectedRowIds={selectedRowIds}
            alerts={alerts}
            clearRowSelection={table.resetRowSelection}
          />
        ) : (
          <AlertPresets
            table={table}
            presetNameFromApi={presetName}
            isLoading={isAsyncLoading}
            presetPrivate={presetPrivate}
            presetNoisy={presetNoisy}
          />
        )}
        {isAsyncLoading && (
          <Callout
            title="Getting your alerts..."
            icon={CircleStackIcon}
            color="gray"
            className="mt-5"
          >
            Alerts will show up in this table as they are added to Keep...
          </Callout>
        )}
        <Table className="mt-4 [&>table]:table-fixed [&>table]:w-full">
          <AlertsTableHeaders
            columns={columns}
            table={table}
            presetName={presetName}
          />
          <AlertsTableBody table={table} showSkeleton={isAsyncLoading} theme={theme} />
        </Table>
        <AlertPagination table={table} isRefreshAllowed={isRefreshAllowed} />
      </Card>
    </>
  );
}
