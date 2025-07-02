import { useRef, useState } from "react";
import clsx from "clsx";
import { Card, Table } from "@tremor/react";
import {
  useAlertTableTheme,
  type AlertDto,
  type ViewedAlert,
} from "@/entities/alerts/model";
import {
  ColumnDef,
  ColumnOrderState,
  ColumnSizingState,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
  VisibilityState,
  GroupingState,
  getGroupedRowModel,
} from "@tanstack/react-table";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import {
  AlertPresetManager,
  evalWithContext,
} from "@/features/presets/presets-manager";
import { AlertSidebar } from "@/features/alerts/alert-detail-sidebar";
import { AlertFacets } from "@/app/(keep)/alerts/[id]/ui/alert-table-alert-facets";
import {
  DynamicFacet,
  FacetFilters,
} from "@/app/(keep)/alerts/[id]/ui/alert-table-facet-types";
import { useConfig } from "@/utils/hooks/useConfig";
import {
  DEFAULT_COLS,
  DEFAULT_COLS_VISIBILITY,
  getColumnsIds,
  getOnlyVisibleCols,
} from "../lib/alert-table-utils";
import { ListFormatOption } from "../lib/alert-table-list-format";
import { TimeFormatOption } from "../lib/alert-table-time-format";
import AlertActions from "./alert-actions";
import AlertsTableHeaders from "./alert-table-headers";
import { TitleAndFilters } from "./TitleAndFilters";
import { AlertsTableBody } from "./alerts-table-body";
// TODO: replace with generic pagination
import AlertPagination from "./alert-pagination";
import { useGroupExpansion } from "@/utils/hooks/useGroupExpansion";
import { PageTitle } from "@/shared/ui";
import SettingsSelection from "./SettingsSelection";

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
  presetStatic?: boolean;
  presetId?: string;
  presetTabs?: PresetTab[];
  isRefreshAllowed?: boolean;
  isMenuColDisplayed?: boolean;
  setDismissedModalAlert?: (alert: AlertDto[] | null) => void;
  mutateAlerts?: () => void;
  setRunWorkflowModalAlert?: (alert: AlertDto) => void;
  setDismissModalAlert?: (alert: AlertDto[] | null) => void;
  setChangeStatusAlert?: (alert: AlertDto) => void;
}

/**
 *
 * @param alerts
 * @param columns
 * @param isAsyncLoading
 * @param presetName
 * @param presetStatic
 * @param presetId
 * @param presetTabs
 * @param isRefreshAllowed
 * @param setDismissedModalAlert
 * @param mutateAlerts
 * @param setRunWorkflowModalAlert
 * @param setDismissModalAlert
 * @param setChangeStatusAlert
 * @constructor
 *
 * @deprecated only used in the history modal, use AlertTableServerSide instead
 */
export function AlertTable({
  alerts,
  columns,
  isAsyncLoading = false,
  presetName,
  presetStatic = false,
  presetId = "",
  presetTabs = [],
  isRefreshAllowed = true,
  setDismissedModalAlert,
  mutateAlerts,
  setRunWorkflowModalAlert,
  setDismissModalAlert,
  setChangeStatusAlert,
}: Props) {
  const a11yContainerRef = useRef<HTMLDivElement>(null);
  const { data: configData } = useConfig();
  const noisyAlertsEnabled = configData?.NOISY_ALERTS_ENABLED;

  const { theme } = useAlertTableTheme();

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

  const [viewedAlerts, setViewedAlerts] = useLocalStorage<ViewedAlert[]>(
    `viewed-alerts-${presetName}`,
    []
  );
  const [clearFiltersTriggered, setClearFiltersTriggered] = useState(false);
  const [lastViewedAlert, setLastViewedAlert] = useState<string | null>(null);

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

  const [columnOrder, setColumnOrder] = useLocalStorage<ColumnOrderState>(
    `column-order-${presetName}`,
    DEFAULT_COLS
  );

  const [columnVisibility, setColumnVisibility] = useLocalStorage<VisibilityState>(
    `column-visibility-${presetName}`,
    DEFAULT_COLS_VISIBILITY
  );

  const [columnSizing, setColumnSizing] = useLocalStorage<ColumnSizingState>(
    "table-sizes",
    {}
  );
  const [columnTimeFormats, setColumnTimeFormats] = useLocalStorage<
    Record<string, TimeFormatOption>
  >(`column-time-formats-${presetName}`, {});

  const [columnListFormats, setColumnListFormats] = useLocalStorage<
    Record<string, ListFormatOption>
  >(`column-list-formats-${presetName}`, {});

  const [sorting, setSorting] = useState<SortingState>(
    noisyAlertsEnabled ? [{ id: "noise", desc: true }] : []
  );

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
  const [isIncidentSelectorOpen, setIsIncidentSelectorOpen] =
    useState<boolean>(false);
  const [isCreateIncidentWithAIOpen, setIsCreateIncidentWithAIOpen] =
    useState<boolean>(false);

  // Add grouping state and group expansion state
  const [grouping, setGrouping] = useState<GroupingState>([]);
  const groupExpansionState = useGroupExpansion(true);
  const { toggleAll, areAllGroupsExpanded } = groupExpansionState;
  const isGroupingActive = grouping.length > 0;

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

  const leftPinnedColumns = noisyAlertsEnabled
    ? ["severity", "checkbox", "status", "source", "name", "noise"]
    : ["severity", "checkbox", "status", "source", "name"];

  const table = useReactTable({
    getRowId: (row) => row.fingerprint,
    data: filteredAlerts,
    columns: columns,
    state: {
      columnVisibility: getOnlyVisibleCols(columnVisibility, columnsIds),
      columnOrder: columnOrder,
      columnSizing: columnSizing,
      columnPinning: {
        left: leftPinnedColumns,
        right: ["alertMenu"],
      },
      sorting: sorting,
      grouping: grouping,
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
    getGroupedRowModel: getGroupedRowModel(),
    onColumnSizingChange: setColumnSizing,
    enableColumnPinning: true,
    columnResizeMode: "onChange",
    autoResetPageIndex: false,
    enableGlobalFilter: true,
    enableSorting: true,
    enableGrouping: true,
    onGroupingChange: setGrouping,
  });

  const selectedAlertsFingerprints = Object.keys(
    table.getSelectedRowModel().rowsById
  );

  let showSkeleton =
    table.getFilteredRowModel().rows.length === 0 && isAsyncLoading;

  const handleRowClick = (alert: AlertDto) => {
    // if presetName is alert-history, do not open sidebar
    if (presetName === "alert-history") {
      return;
    }

    // Update viewed alerts
    setViewedAlerts((prev) => {
      const newViewedAlerts = prev.filter(
        (a) => a.fingerprint !== alert.fingerprint
      );
      return [
        ...newViewedAlerts,
        {
          fingerprint: alert.fingerprint,
          viewedAt: new Date().toISOString(),
        },
      ];
    });

    setLastViewedAlert(alert.fingerprint);
    setSelectedAlert(alert);
    setIsSidebarOpen(true);
  };

  // Reset last viewed alert when sidebar closes
  const handleSidebarClose = () => {
    setIsSidebarOpen(false);
  };

  // Wrapper functions to maintain sync behavior for deprecated component
  const handleColumnOrderChange = (newOrder: ColumnOrderState) => {
    setColumnOrder(newOrder);
  };

  const handleColumnVisibilityChange = (newVisibility: VisibilityState) => {
    setColumnVisibility(newVisibility);
  };

  return (
    <div className="h-screen flex flex-col gap-4">
      <div className="px-4 flex-none">
        <TitleAndFilters
          table={table}
          alerts={alerts}
          presetName={presetName}
        />
      </div>

      <div className="h-14 px-4 flex-none">
        {selectedAlertsFingerprints.length ? (
          <AlertActions
            selectedAlertsFingerprints={selectedAlertsFingerprints}
            table={table}
            clearRowSelection={table.resetRowSelection}
            setDismissModalAlert={setDismissedModalAlert}
            mutateAlerts={mutateAlerts}
            setIsIncidentSelectorOpen={setIsIncidentSelectorOpen}
            isIncidentSelectorOpen={isIncidentSelectorOpen}
            setIsCreateIncidentWithAIOpen={setIsCreateIncidentWithAIOpen}
            isCreateIncidentWithAIOpen={isCreateIncidentWithAIOpen}
          />
        ) : (
          <AlertPresetManager 
            table={table} 
            presetName={presetName}
            isGroupingActive={isGroupingActive}
            onToggleAllGroups={toggleAll}
            areAllGroupsExpanded={areAllGroupsExpanded}
          />
        )}
      </div>

      <div className="flex-grow px-4 pb-4">
        <div className="h-full flex gap-4">
          <div className="w-32 min-w-[12rem] overflow-y-auto">
            <AlertFacets
              className="sticky top-0"
              alerts={alerts}
              facetFilters={facetFilters}
              setFacetFilters={setFacetFilters}
              dynamicFacets={dynamicFacets}
              setDynamicFacets={setDynamicFacets}
              onDelete={handleFacetDelete}
              table={table}
              showSkeleton={showSkeleton}
            />
          </div>

          <div className="flex-1 flex flex-col min-w-0">
            <Card className="h-full flex flex-col p-0 overflow-x-auto">
              <div className="flex-grow flex flex-col">
                <div ref={a11yContainerRef} className="sr-only" />

                <div className="flex-grow">
                  <Table
                    className={clsx(
                      "[&>table]:table-fixed [&>table]:w-full",
                      "overflow-x-auto",
                      "w-full"
                    )}
                  >
                    <AlertsTableHeaders
                      columns={columns}
                      table={table}
                      presetName={presetName}
                      a11yContainerRef={a11yContainerRef}
                      columnTimeFormats={columnTimeFormats}
                      setColumnTimeFormats={setColumnTimeFormats}
                      columnListFormats={columnListFormats}
                      setColumnListFormats={setColumnListFormats}
                      columnOrder={columnOrder}
                      setColumnOrder={handleColumnOrderChange}
                      columnVisibility={columnVisibility}
                      setColumnVisibility={handleColumnVisibilityChange}
                      columnRenameMapping={{}}
                      setColumnRenameMapping={() => {}}
                    />
                    <AlertsTableBody
                      table={table}
                      showSkeleton={showSkeleton}
                      theme={theme}
                      onRowClick={handleRowClick}
                      lastViewedAlert={lastViewedAlert}
                      presetName={presetName}
                      groupExpansionState={groupExpansionState}
                    />
                  </Table>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>

      <div className="h-16 px-4 flex-none pl-[14rem]">
        <AlertPagination
          table={table}
          presetName={presetName}
          isRefreshAllowed={isRefreshAllowed}
        />
      </div>

      <AlertSidebar
        isOpen={isSidebarOpen}
        toggle={handleSidebarClose}
        alert={selectedAlert}
        setRunWorkflowModalAlert={setRunWorkflowModalAlert}
        setDismissModalAlert={setDismissModalAlert}
        setChangeStatusAlert={setChangeStatusAlert}
        setIsIncidentSelectorOpen={() => {
          if (selectedAlert) {
            table
              .getRowModel()
              .rows.find(
                (row) => row.original.fingerprint === selectedAlert.fingerprint
              )
              ?.toggleSelected();
            setIsIncidentSelectorOpen(true);
          }
        }}
      />
    </div>
  );
}
