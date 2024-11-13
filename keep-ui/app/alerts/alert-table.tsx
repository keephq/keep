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
import { AlertFacets } from "./alert-table-alert-facets";
import { FacetFilters } from "./alert-table-facet-types";
import { DynamicFacet } from "./alert-table-facet-dynamic";

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
  presetId = "",
  presetTabs = [],
  isRefreshAllowed = true,
  setDismissedModalAlert,
  mutateAlerts,
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

  const [facetFilters, setFacetFilters] = useLocalStorage<FacetFilters>(
    `alertFacetFilters-${presetName}`,
    {
      severity: [],
      status: [],
      source: [],
      assignee: [],
      dismissed: [],
      incident: [],
    }
  );

  const [dynamicFacets, setDynamicFacets] = useLocalStorage<DynamicFacet[]>(
    `dynamicFacets-${presetName}`,
    []
  );

  const handleFacetDelete = (facetKey: string) => {
    setDynamicFacets((prevFacets) =>
      prevFacets.filter((df) => df.key !== facetKey)
    );
    setFacetFilters((prevFilters) => {
      const newFilters = { ...prevFilters };
      delete newFilters[facetKey];
      return newFilters;
    });
  };

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
      id: tab.id,
    })),
    { name: "+", filter: (alert: AlertDto) => true }, // a special tab to add new tabs
  ]);

  const [selectedTab, setSelectedTab] = useState(0);
  const [selectedAlert, setSelectedAlert] = useState<AlertDto | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const filteredAlerts = alerts.filter((alert) => {
    // First apply tab filter
    if (!tabs[selectedTab].filter(alert)) {
      return false;
    }

    // Then apply facet filters
    return Object.entries(facetFilters).every(([facetKey, includedValues]) => {
      // If no values are included, don't filter
      if (includedValues.length === 0) {
        return true;
      }

      let value;
      if (facetKey.includes(".")) {
        // Handle nested keys like "labels.job"
        const [parentKey, childKey] = facetKey.split(".");
        const parentValue = alert[parentKey as keyof AlertDto];

        if (
          typeof parentValue === "object" &&
          parentValue !== null &&
          !Array.isArray(parentValue) &&
          !(parentValue instanceof Date)
        ) {
          value = (parentValue as Record<string, unknown>)[childKey];
        }
      } else {
        value = alert[facetKey as keyof AlertDto];
      }

      // Handle source array separately
      if (facetKey === "source") {
        const sources = value as string[];

        // Check if n/a is selected and sources is empty/null
        if (includedValues.includes("n/a")) {
          return !sources || sources.length === 0;
        }

        return (
          Array.isArray(sources) &&
          sources.some((source) => includedValues.includes(source))
        );
      }

      // Handle n/a cases for other facets
      if (includedValues.includes("n/a")) {
        return value === null || value === undefined || value === "";
      }

      // For non-n/a cases, convert value to string for comparison
      // Skip null/undefined values as they should only match n/a
      if (value === null || value === undefined || value === "") {
        return false;
      }

      return includedValues.includes(String(value));
    });
  });

  const handleFacetSelect = (
    facetKey: string,
    value: string,
    exclusive: boolean,
    isAllOnly: boolean = false
  ) => {
    setFacetFilters((prev) => {
      // Handle All/Only button clicks
      if (isAllOnly) {
        if (value === "") {
          // Reset to include all values (empty array)
          return {
            ...prev,
            [facetKey]: [],
          };
        }

        if (exclusive) {
          // Only include this value
          return {
            ...prev,
            [facetKey]: [value],
          };
        }
      }

      // Handle regular checkbox clicks
      const currentValues = prev[facetKey] || [];

      if (currentValues.length === 0) {
        // If no filters, clicking one value means we want to exclude that value
        // So we need to include all OTHER values
        const allValues = new Set(
          alerts
            .map((alert) => {
              const val = alert[facetKey as keyof AlertDto];
              return Array.isArray(val) ? val : [String(val)];
            })
            .flat()
        );
        return {
          ...prev,
          [facetKey]: Array.from(allValues).filter((v) => v !== value),
        };
      }

      if (currentValues.includes(value)) {
        // Remove value if it's already included
        const newValues = currentValues.filter((v) => v !== value);
        return {
          ...prev,
          [facetKey]: newValues,
        };
      } else {
        // Add value if it's not included
        return {
          ...prev,
          [facetKey]: [...currentValues, value],
        };
      }
    });
  };

  const table = useReactTable({
    data: filteredAlerts,
    columns: columns,
    state: {
      columnVisibility: getOnlyVisibleCols(columnVisibility, columnsIds),
      columnOrder: columnOrder,
      columnSizing: columnSizing,
      columnPinning: {
        left: ["severity", "checkbox", "noise"],
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
      <div className="flex flex-grow gap-6">
        <div className="w-32 min-w-[12rem] mt-16">
          <AlertFacets
            className="sticky top-0"
            alerts={alerts}
            facetFilters={facetFilters}
            setFacetFilters={setFacetFilters}
            dynamicFacets={dynamicFacets}
            setDynamicFacets={setDynamicFacets}
            onDelete={handleFacetDelete}
            table={table}
          />
        </div>
        {/* Using p-4 -m-4 to set overflow-hidden without affecting shadow */}
        <div className="flex flex-col gap-4 overflow-hidden p-4 -m-4">
          <div className="min-h-10">
            {/* Setting min-h-10 to avoid jumping when actions are shown */}
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
          </div>
          <Card className="flex-grow h-full flex flex-col p-0">
            <div className="flex-grow">
              {isAsyncLoading && (
                <Callout
                  title="Getting your alerts..."
                  icon={CircleStackIcon}
                  color="gray"
                  className="m-5"
                >
                  Alerts will show up in this table as they are added to Keep...
                </Callout>
              )}
              {/* For dynamic preset, add alert tabs*/}
              {!presetStatic && (
                <AlertTabs
                  presetId={presetId}
                  tabs={tabs}
                  setTabs={setTabs}
                  selectedTab={selectedTab}
                  setSelectedTab={setSelectedTab}
                />
              )}
              <Table className="flex-grow overflow-auto [&>table]:table-fixed [&>table]:w-full">
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
            </div>
          </Card>
        </div>
      </div>
      <div className="mt-2 mb-8 pl-[14rem]">
        <AlertPagination
          table={table}
          presetName={presetName}
          isRefreshAllowed={isRefreshAllowed}
        />
      </div>
      <AlertSidebar
        isOpen={isSidebarOpen}
        toggle={() => setIsSidebarOpen(false)}
        alert={selectedAlert}
      />
    </div>
  );
}
