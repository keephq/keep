import { useEffect, useState } from "react";
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
import AlertTabs from "./alert-tabs";
import AlertSidebar from "./alert-sidebar";

interface PresetTab {
  name: string;
  filter: string;
  id?: string;
}
interface Props {
  alerts: AlertDto[];
  columns: ColumnDef<AlertDto>[];
  isAsyncLoading?: boolean;
  presetName: string;
  presetPrivate?: boolean;
  presetNoisy?: boolean;
  presetStatic?: boolean;
  presetId?: string;
  presetTabs?: PresetTab[];
  isRefreshAllowed?: boolean;
  isMenuColDisplayed?: boolean;
  setDismissedModalAlert?: (alert: AlertDto[] | null) => void;
  mutateAlerts?: () => void;
}

export function AlertTable({
  alerts,
  columns,
  isAsyncLoading = false,
  presetName,
  presetPrivate = false,
  presetNoisy = false,
  presetStatic = false,
  presetId = '',
  presetTabs = [],
  isRefreshAllowed = true,
  setDismissedModalAlert,
  mutateAlerts
}: Props) {
  const [theme, setTheme] = useLocalStorage(
    "alert-table-theme",
    Object.values(severityMapping).reduce<{ [key: string]: string }>(
      (acc, severity) => {
        acc[severity] = "bg-white";
        return acc;
      },
      {}
    )
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

  const [sorting, setSorting] = useState<SortingState>([
    { id: "noise", desc: true },
  ]);

  const [tabs, setTabs] = useState([
    { name: "All", filter: (alert: AlertDto) => true },
    ...presetTabs.map((tab) => ({
      name: tab.name,
      filter: (alert: AlertDto) => evalWithContext(alert, tab.filter),
      id: tab.id
    })),
    { name: "+", filter: (alert: AlertDto) => true }, // a special tab to add new tabs
  ]);

  const [selectedTab, setSelectedTab] = useState(0);
  const [selectedAlert, setSelectedAlert] = useState<AlertDto | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const filteredAlerts = alerts.filter(tabs[selectedTab].filter);

  const table = useReactTable({
    data: filteredAlerts,
    columns: columns,
    state: {
      columnVisibility: getOnlyVisibleCols(columnVisibility, columnsIds),
      columnOrder: columnOrder,
      columnSizing: columnSizing,
      columnPinning: {
        left: ["noise", "checkbox"],
        right: ["alertMenu"],
      },
      sorting: sorting,
    },
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    initialState: {
      pagination: { pageSize: 20 },
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

  // show skeleton if no alerts are loaded
  let showSkeleton = table.getFilteredRowModel().rows.length === 0;
  // if showSkeleton and not loading, show empty state
  let showEmptyState = !isAsyncLoading && showSkeleton;

  const handleRowClick = (alert: AlertDto) => {
    // if presetName is alert-history, do not open sidebar
    if (presetName === "alert-history") {
      return;
    }
    setSelectedAlert(alert);
    setIsSidebarOpen(true);
  };

  return (
    <div className="flex flex-col h-full">
      <TitleAndFilters
        table={table}
        alerts={alerts}
        presetName={presetName}
        onThemeChange={handleThemeChange}
      />
      <Card className="flex-grow h-full flex flex-col mt-4 px-4 pt-6 overflow-hidden">
        {selectedRowIds.length ? (
          <AlertActions
            selectedRowIds={selectedRowIds}
            alerts={alerts}
            clearRowSelection={table.resetRowSelection}
            setDismissModalAlert={setDismissedModalAlert}
            mutateAlerts={mutateAlerts}
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
        {/* For dynamic preset, add alert tabs*/}
        { !presetStatic &&
          <AlertTabs presetId={presetId} tabs={tabs} setTabs={setTabs} selectedTab={selectedTab} setSelectedTab={setSelectedTab} />
        }
        <Table className="flex-grow mt-4 overflow-auto [&>table]:table-fixed [&>table]:w-full">
          <AlertsTableHeaders
            columns={columns}
            table={table}
            presetName={presetName}
          />
          <AlertsTableBody
            table={table}
            showSkeleton={showSkeleton}
            showEmptyState={showEmptyState}
            theme={theme}
            onRowClick={handleRowClick}
            presetName={presetName}
          />
        </Table>
      </Card>
      <div className="mt-2 mb-8">
        <AlertPagination table={table} presetName={presetName} isRefreshAllowed={isRefreshAllowed} />
      </div>
      <AlertSidebar
        isOpen={isSidebarOpen}
        toggle={() => setIsSidebarOpen(false)}
        alert={selectedAlert}
      />
    </div>
  );
}
