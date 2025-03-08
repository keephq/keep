import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Table, Card, Button } from "@tremor/react";
import { AlertsTableBody } from "./alerts-table-body";
import { AlertDto, reverseSeverityMapping } from "@/entities/alerts/model";
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
  PaginationState,
} from "@tanstack/react-table";
import { ListFormatOption } from "./alert-table-list-format";
import AlertsTableHeaders from "./alert-table-headers";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import {
  getColumnsIds,
  getOnlyVisibleCols,
  DEFAULT_COLS_VISIBILITY,
  DEFAULT_COLS,
} from "./alert-table-utils";
import AlertActions from "./alert-actions";
import { AlertPresetManager } from "./alert-preset-manager";
import { evalWithContext } from "./alerts-rules-builder";
import { TitleAndFilters } from "./TitleAndFilters";
import { severityMapping } from "@/entities/alerts/model";
import AlertSidebar from "./alert-sidebar";
import { useConfig } from "@/utils/hooks/useConfig";
import { FacetsPanelServerSide } from "@/features/filter/facet-panel-server-side";
import Image from "next/image";
import { EmptyStateCard, SeverityBorderIcon, UISeverity } from "@/shared/ui";
import { useUser } from "@/entities/users/model/useUser";
import { UserStatefulAvatar } from "@/entities/users/ui";
import { getStatusIcon, getStatusColor } from "@/shared/lib/status-utils";
import { Icon } from "@tremor/react";
import {
  BellIcon,
  BellSlashIcon,
  FunnelIcon,
  MagnifyingGlassIcon,
} from "@heroicons/react/24/outline";
import AlertPaginationServerSide from "./alert-pagination-server-side";
import { FacetDto } from "@/features/filter";
import { GroupingState, getGroupedRowModel } from "@tanstack/react-table";
import { TimeFrame } from "@/components/ui/DateRangePicker";
import { AlertsQuery } from "@/utils/hooks/useAlerts";
import { v4 as uuidV4 } from "uuid";
import { FacetsConfig } from "@/features/filter/models";
import { ViewedAlert } from "./alert-table";
import { TimeFormatOption } from "./alert-table-time-format";
import PushAlertToServerModal from "./alert-push-alert-to-server-modal";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { GrTest } from "react-icons/gr";
import { PlusIcon } from "@heroicons/react/20/solid";
import { DynamicImageProviderIcon } from "@/components/ui";
import { useAlertRowStyle } from "@/entities/alerts/model/useAlertRowStyle";

const AssigneeLabel = ({ email }: { email: string }) => {
  const user = useUser(email);
  return user ? user.name : email;
};

interface PresetTab {
  name: string;
  filter: string;
  id?: string;
}

interface Tab {
  name: string;
  filter: (alert: AlertDto) => boolean;
  id?: string;
}

interface Props {
  refreshToken: string | null;
  alerts: AlertDto[];
  initialFacets: FacetDto[];
  alertsTotalCount: number;
  columns: ColumnDef<AlertDto>[];
  isAsyncLoading?: boolean;
  presetName: string;
  presetTabs?: PresetTab[];
  isRefreshAllowed?: boolean;
  isMenuColDisplayed?: boolean;
  setDismissedModalAlert?: (alert: AlertDto[] | null) => void;
  mutateAlerts?: () => void;
  setRunWorkflowModalAlert?: (alert: AlertDto) => void;
  setDismissModalAlert?: (alert: AlertDto[] | null) => void;
  setChangeStatusAlert?: (alert: AlertDto) => void;
  onReload?: (query: AlertsQuery) => void;
  onPoll?: () => void;
  onQueryChange?: () => void;
  onLiveUpdateStateChange?: (isLiveUpdateEnabled: boolean) => void;
}

export function AlertTableServerSide({
  refreshToken,
  alerts,
  alertsTotalCount,
  columns,
  initialFacets,
  isAsyncLoading = false,
  presetName,
  presetTabs = [],
  isRefreshAllowed = true,
  setDismissedModalAlert,
  mutateAlerts,
  setRunWorkflowModalAlert,
  setDismissModalAlert,
  setChangeStatusAlert,
  onReload,
  onPoll,
  onQueryChange,
  onLiveUpdateStateChange,
}: Props) {
  const [clearFiltersToken, setClearFiltersToken] = useState<string | null>(
    null
  );
  const [grouping, setGrouping] = useState<GroupingState>([]);
  const [facetsPanelRefreshToken, setFacetsPanelRefreshToken] = useState<
    string | null
  >(null);
  const [shouldRefreshDate, setShouldRefreshDate] = useState<boolean>(false);
  const [filterCel, setFilterCel] = useState<string>("");
  const [searchCel, setSearchCel] = useState<string>("");
  const [dateRangeCel, setDateRangeCel] = useState<string>("");
  const [dateRange, setDateRange] = useState<TimeFrame | null>(null);
  const alertsQueryRef = useRef<AlertsQuery | null>(null);
  const [rowStyle] = useAlertRowStyle();
  const [columnTimeFormats, setColumnTimeFormats] = useLocalStorage<
    Record<string, TimeFormatOption>
  >(`column-time-formats-${presetName}`, {});
  const a11yContainerRef = useRef<HTMLDivElement>(null);
  const { data: configData } = useConfig();
  const noisyAlertsEnabled = configData?.NOISY_ALERTS_ENABLED;

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

  const [columnListFormats, setColumnListFormats] = useLocalStorage<
    Record<string, ListFormatOption>
  >(`column-list-formats-${presetName}`, {});

  const [columnSizing, setColumnSizing] = useLocalStorage<ColumnSizingState>(
    "table-sizes",
    {}
  );

  const handleThemeChange = (newTheme: any) => {
    setTheme(newTheme);
  };

  const [sorting, setSorting] = useState<SortingState>(
    noisyAlertsEnabled ? [{ id: "noise", desc: true }] : []
  );
  const [paginationState, setPaginationState] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: rowStyle == "relaxed" ? 20 : 50,
  });

  const [, setViewedAlerts] = useLocalStorage<ViewedAlert[]>(
    `viewed-alerts-${presetName}`,
    []
  );
  const [lastViewedAlert, setLastViewedAlert] = useState<string | null>(null);

  useEffect(() => {
    const filterArray = [];

    if (dateRange?.start) {
      filterArray.push(`lastReceived >= '${dateRange.start.toISOString()}'`);
    }

    if (dateRange?.paused && dateRange?.end) {
      filterArray.push(`lastReceived <= '${dateRange.end.toISOString()}'`);
    }

    setDateRangeCel(filterArray.filter(Boolean).join(" && "));

    // makes alerts to refresh when not paused and all time is selected
    if (!dateRange?.start && !dateRange?.end && !dateRange?.paused) {
      setTimeout(() => {
        onReload && onReload(alertsQueryRef.current as AlertsQuery);
        setFacetsPanelRefreshToken(uuidV4());
      }, 100);
    }
  }, [dateRange]);

  const mainCelQuery = useMemo(() => {
    const filterArray = [dateRangeCel, searchCel];
    return filterArray.filter(Boolean).join(" && ");
  }, [searchCel, dateRangeCel]);

  const alertsQuery = useMemo(
    function whenQueryChange() {
      let resultCel = [mainCelQuery, filterCel].filter(Boolean).join(" && ");

      const limit = paginationState.pageSize;
      const offset = limit * paginationState.pageIndex;
      const alertsQuery: AlertsQuery = {
        cel: resultCel,
        offset,
        limit,
        sortBy: sorting[0]?.id,
        sortDirection: sorting[0]?.desc ? "DESC" : "ASC",
      };

      alertsQueryRef.current = alertsQuery;
      return alertsQuery;
    },
    [filterCel, mainCelQuery, paginationState, sorting]
  );

  useEffect(() => {
    onQueryChange && onQueryChange();
  }, [filterCel, searchCel, paginationState, sorting, onQueryChange]);

  useEffect(() => {
    onReload && onReload(alertsQueryRef.current as AlertsQuery);
  }, [alertsQuery, onReload]);

  const [tabs, setTabs] = useState<Tab[]>([
    { name: "All", filter: () => true },
    ...presetTabs.map((tab) => ({
      name: tab.name,
      filter: (alert: AlertDto) => evalWithContext(alert, tab.filter),
      id: tab.id,
    })),
    { name: "+", filter: () => true },
  ]);

  const [selectedTab, setSelectedTab] = useState(0);
  const [selectedAlert, setSelectedAlert] = useState<AlertDto | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isIncidentSelectorOpen, setIsIncidentSelectorOpen] =
    useState<boolean>(false);

  const leftPinnedColumns = noisyAlertsEnabled
    ? ["severity", "checkbox", "source", "name", "noise"]
    : ["severity", "checkbox", "source", "name"];

  const table = useReactTable({
    getRowId: (row) => row.fingerprint,
    data: alerts,
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
      pagination: {
        pageIndex: paginationState.pageIndex,
        pageSize: paginationState.pageSize,
      },
    },
    meta: {
      columnTimeFormats: columnTimeFormats,
      setColumnTimeFormats: setColumnTimeFormats,
    },
    enableGrouping: true,
    manualSorting: true,
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    initialState: {
      pagination: { pageSize: rowStyle == "relaxed" ? 20 : 50 },
    },
    globalFilterFn: ({ original }, _id, value) => {
      return evalWithContext(original, value);
    },
    getGroupedRowModel: getGroupedRowModel(),
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onColumnSizingChange: setColumnSizing,
    enableColumnPinning: true,
    columnResizeMode: "onChange",
    autoResetPageIndex: false,
    enableGlobalFilter: true,
    enableSorting: true,
    manualPagination: true,
    pageCount: Math.ceil(alertsTotalCount / paginationState.pageSize),
    onPaginationChange: setPaginationState,
    onGroupingChange: setGrouping,
  });

  const selectedAlertsFingerprints = Object.keys(table.getState().rowSelection);

  let showSkeleton = isAsyncLoading;
  const isTableEmpty = table.getPageCount() === 0;
  const showFilterEmptyState = isTableEmpty && !!filterCel;
  const showSearchEmptyState =
    isTableEmpty && !!searchCel && !showFilterEmptyState;

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

  useEffect(() => {
    // When refresh token comes, this code allows polling for certain time and then stops.
    // Will start polling again when new refresh token comes.
    // Why? Because events are throttled on BE side but we want to refresh the data frequently
    // when keep gets ingested with data, and it requires control when to refresh from the UI side.
    if (refreshToken) {
      setShouldRefreshDate(true);
      const timeout = setTimeout(() => {
        setShouldRefreshDate(false);
      }, 15000);
      return () => clearTimeout(timeout);
    }
  }, [refreshToken]);

  const timeframeChanged = useCallback(
    (timeframe: TimeFrame | null) => {
      if (!timeframe) {
        setDateRange(null);
        return;
      }

      if (timeframe?.paused != dateRange?.paused) {
        onLiveUpdateStateChange && onLiveUpdateStateChange(!timeframe.paused);
      }

      const currentDiff =
        (dateRange?.end?.getTime() || 0) - (dateRange?.start?.getTime() || 0);
      const newDiff =
        (timeframe?.end?.getTime() || 0) - (timeframe?.start?.getTime() || 0);

      if (!timeframe?.paused && currentDiff === newDiff) {
        if (shouldRefreshDate) {
          onPoll && onPoll();
          setDateRange(timeframe);
        }
        return;
      }

      onQueryChange && onQueryChange();
      setDateRange(timeframe);
    },
    [dateRange, shouldRefreshDate, onLiveUpdateStateChange]
  );

  const facetsConfig: FacetsConfig = useMemo(() => {
    return {
      ["Severity"]: {
        canHitEmptyState: false,
        renderOptionLabel: (facetOption) => {
          const label =
            severityMapping[Number(facetOption.display_name)] ||
            facetOption.display_name;
          return <span className="capitalize">{label}</span>;
        },
        renderOptionIcon: (facetOption) => (
          <SeverityBorderIcon
            severity={
              (severityMapping[Number(facetOption.display_name)] ||
                facetOption.display_name) as UISeverity
            }
          />
        ),
        sortCallback: (facetOption) =>
          reverseSeverityMapping[facetOption.value] || 100, // if status is not in the mapping, it should be at the end
      },
      ["Status"]: {
        renderOptionIcon: (facetOption) => (
          <Icon
            icon={getStatusIcon(facetOption.display_name)}
            size="sm"
            color={getStatusColor(facetOption.display_name)}
            className="!p-0"
          />
        ),
      },
      ["Source"]: {
        renderOptionIcon: (facetOption) => {
          if (facetOption.display_name === "None") {
            return;
          }

          return (
            <DynamicImageProviderIcon
              className="inline-block"
              alt={facetOption.display_name}
              height={16}
              width={16}
              providerType={facetOption.display_name}
              title={facetOption.display_name}
              src={
                facetOption.display_name.includes("@")
                  ? "/icons/mailgun-icon.png"
                  : `/icons/${facetOption.display_name}-icon.png`
              }
            />
          );
        },
      },
      ["Assignee"]: {
        renderOptionIcon: (facetOption) => (
          <UserStatefulAvatar email={facetOption.display_name} size="xs" />
        ),
        renderOptionLabel: (facetOption) => {
          if (facetOption.display_name === "null") {
            return "Not assigned";
          }
          return <AssigneeLabel email={facetOption.display_name} />;
        },
      },
      ["Dismissed"]: {
        renderOptionLabel: (facetOption) =>
          facetOption.display_name.toLocaleLowerCase() === "true"
            ? "Dismissed"
            : "Not dismissed",
        renderOptionIcon: (facetOption) => (
          <Icon
            icon={
              facetOption.display_name.toLocaleLowerCase() === "true"
                ? BellSlashIcon
                : BellIcon
            }
            size="sm"
            className="text-gray-600 !p-0"
          />
        ),
      },
    };
  }, []);

  const [isCreateIncidentWithAIOpen, setIsCreateIncidentWithAIOpen] =
    useState<boolean>(false);
  const router = useRouter();
  const pathname = usePathname();
  // handle "create incident with AI from last 25 alerts" if ?createIncidentsFromLastAlerts=25
  const searchParams = useSearchParams();
  useEffect(() => {
    if (alerts.length === 0 && selectedAlertsFingerprints.length) {
      return;
    }

    const lastAlertsCount = searchParams.get("createIncidentsFromLastAlerts");
    const lastAlertsNumber = lastAlertsCount
      ? parseInt(lastAlertsCount)
      : undefined;
    if (!lastAlertsNumber) {
      return;
    }

    const lastAlerts = table.getRowModel().rows.slice(-lastAlertsNumber);
    const alertsFingerprints = lastAlerts.map(
      (alert) => alert.original.fingerprint
    );

    table.setRowSelection(
      alertsFingerprints.reduce(
        (acc, fingerprint) => {
          acc[fingerprint] = true;
          return acc;
        },
        {} as Record<string, boolean>
      )
    );
    const searchParamsWithoutCreateIncidentsFromLastAlerts =
      new URLSearchParams(searchParams);
    searchParamsWithoutCreateIncidentsFromLastAlerts.delete(
      "createIncidentsFromLastAlerts"
    );
    setIsCreateIncidentWithAIOpen(true);
    // todo: remove searchParams after reading
    router.replace(
      pathname +
        "?" +
        searchParamsWithoutCreateIncidentsFromLastAlerts.toString()
    );
    // call create incident with AI from last 25 alerts
    // api/incidents?createIncidentsFromLastAlerts=25
  }, [alerts.length, searchParams, table]);

  //

  const [modalOpen, setModalOpen] = useState(false);

  const handleModalClose = () => setModalOpen(false);
  const handleModalOpen = () => setModalOpen(true);
  function renderTable() {
    if (
      !showSkeleton &&
      table.getPageCount() === 0 &&
      !showFilterEmptyState &&
      !showSearchEmptyState
    ) {
      return (
        <>
          <div className="flex-1 flex items-center w-full">
            <div className="flex flex-col justify-center items-center w-full p-4">
              <EmptyStateCard
                noCard
                title="No Alerts to Display"
                description="Connect a data source to start receiving alerts, or simulate an alert to test the platform"
              >
                <div className="flex gap-2 justify-center">
                  <Button
                    color="orange"
                    icon={GrTest}
                    variant="secondary"
                    onClick={handleModalOpen}
                  >
                    Simulate Alert
                  </Button>
                  <Button
                    icon={PlusIcon}
                    color="orange"
                    variant="primary"
                    onClick={() => {
                      router.push("/providers?labels=alert");
                    }}
                  >
                    Connect Data Source
                  </Button>
                </div>
              </EmptyStateCard>
            </div>
          </div>
          <PushAlertToServerModal
            isOpen={modalOpen}
            handleClose={handleModalClose}
            presetName={presetName}
          />
        </>
      );
    }
    if (!showSkeleton) {
      if (showFilterEmptyState) {
        return (
          <>
            <div className="flex-1 flex items-center h-full w-full">
              <div className="flex flex-col justify-center items-center w-full p-4">
                <EmptyStateCard
                  noCard
                  title="No Alerts Matching Your Filter"
                  description="Reset filter to see all alerts"
                  icon={FunnelIcon}
                >
                  <Button
                    color="orange"
                    variant="secondary"
                    onClick={() => setClearFiltersToken(uuidV4())}
                  >
                    Reset filter
                  </Button>
                </EmptyStateCard>
              </div>
            </div>
          </>
        );
      }

      if (showSearchEmptyState) {
        return (
          <>
            <div className="flex-1 flex items-center h-full w-full">
              <div className="flex flex-col justify-center items-center w-full p-4">
                <EmptyStateCard
                  noCard
                  title="No Alerts Matching Your CEL Query"
                  description="Check your CEL query and try again"
                  icon={MagnifyingGlassIcon}
                />
              </div>
            </div>
          </>
        );
      }
    }
    return (
      <Table className="[&>table]:table-fixed [&>table]:w-full">
        <AlertsTableHeaders
          columns={columns}
          table={table}
          presetName={presetName}
          a11yContainerRef={a11yContainerRef}
          columnTimeFormats={columnTimeFormats}
          setColumnTimeFormats={setColumnTimeFormats}
          columnListFormats={columnListFormats}
          setColumnListFormats={setColumnListFormats}
        />
        <AlertsTableBody
          table={table}
          showSkeleton={showSkeleton}
          theme={theme}
          lastViewedAlert={lastViewedAlert}
          onRowClick={handleRowClick}
        />
      </Table>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex-none">
        <TitleAndFilters
          table={table}
          alerts={alerts}
          timeframeRefreshInterval={2000}
          liveUpdateOptionEnabled={true}
          presetName={presetName}
          onThemeChange={handleThemeChange}
          onTimeframeChange={timeframeChanged}
        />
      </div>

      {/* Make actions/presets section fixed height */}
      <div className="h-14 flex-none">
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
            presetName={presetName}
            onCelChanges={setSearchCel}
            table={table}
          />
        )}
      </div>

      <div className="pb-4">
        <div className="flex gap-4">
          {/* Facets sidebar */}
          <div className="w-33 min-w-[12rem] overflow-y-auto">
            <FacetsPanelServerSide
              key={searchCel}
              usePropertyPathsSuggestions={true}
              entityName={"alerts"}
              facetOptionsCel={mainCelQuery}
              clearFiltersToken={clearFiltersToken}
              initialFacetsData={{ facets: initialFacets, facetOptions: null }}
              facetsConfig={facetsConfig}
              onCelChange={setFilterCel}
              revalidationToken={facetsPanelRefreshToken}
            />
          </div>

          {/* Table section */}
          <div className="flex-1 flex flex-col min-w-0 gap-4">
            <Card className="flex-1 flex flex-col p-0 overflow-x-auto">
              <div className="flex-1 flex flex-col">
                <div ref={a11yContainerRef} className="sr-only" />

                {/* Make table wrapper scrollable */}
                <div data-testid="alerts-table" className="flex-1">
                  {renderTable()}
                </div>
              </div>
            </Card>
            {/* Pagination footer - fixed height */}
            <div className="h-16 flex-none">
              <AlertPaginationServerSide
                table={table}
                isRefreshing={isAsyncLoading}
                isRefreshAllowed={isRefreshAllowed}
                onRefresh={() =>
                  onReload && onReload(alertsQueryRef.current as AlertsQuery)
                }
              />
            </div>
          </div>
        </div>
      </div>

      <AlertSidebar
        isOpen={isSidebarOpen}
        toggle={() => setIsSidebarOpen(false)}
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
