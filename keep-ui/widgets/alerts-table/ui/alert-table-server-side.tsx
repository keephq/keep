import { useEffect, useMemo, useRef, useState } from "react";
import { Table, Card, Button } from "@tremor/react";
import { AlertsTableBody } from "@/widgets/alerts-table/ui/alerts-table-body";
import {
  AlertDto,
  AlertsQuery,
  reverseSeverityMapping,
  ViewedAlert,
} from "@/entities/alerts/model";
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
import { ListFormatOption } from "@/widgets/alerts-table/lib/alert-table-list-format";
import AlertsTableHeaders from "@/widgets/alerts-table/ui/alert-table-headers";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import {
  getColumnsIds,
  getOnlyVisibleCols,
  DEFAULT_COLS_VISIBILITY,
  DEFAULT_COLS,
} from "@/widgets/alerts-table/lib/alert-table-utils";
import AlertActions from "@/widgets/alerts-table/ui/alert-actions";
import {
  AlertPresetManager,
  evalWithContext,
} from "@/features/presets/presets-manager";
import { severityMapping } from "@/entities/alerts/model";
import { AlertSidebar } from "@/features/alerts/alert-detail-sidebar";
import { useConfig } from "@/utils/hooks/useConfig";
import { FacetsPanelServerSide } from "@/features/filter/facet-panel-server-side";
import {
  EmptyStateCard,
  PageTitle,
  SeverityBorderIcon,
  UISeverity,
} from "@/shared/ui";
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
import { FacetDto, Pagination } from "@/features/filter";
import { GroupingState, getGroupedRowModel } from "@tanstack/react-table";
import { v4 as uuidV4 } from "uuid";
import { FacetsConfig } from "@/features/filter/models";
import { TimeFormatOption } from "@/widgets/alerts-table/lib/alert-table-time-format";
import { PushAlertToServerModal } from "@/features/alerts/simulate-alert";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { GrTest } from "react-icons/gr";
import { PlusIcon } from "@heroicons/react/20/solid";
import { DynamicImageProviderIcon } from "@/components/ui";
import { useAlertRowStyle, useAlertTableTheme } from "@/entities/alerts/model";
import { useIsShiftKeyHeld } from "@/features/keyboard-shortcuts";
import SettingsSelection from "./SettingsSelection";
import EnhancedDateRangePickerV2, {
  AllTimeFrame,
} from "@/components/ui/DateRangePickerV2";
import { AlertsTableDataQuery } from "./useAlertsTableData";
import { useTimeframeState } from "@/components/ui/useTimeframeState";
import { PaginationState } from "@/features/filter/pagination";
import { useGroupExpansion } from "@/utils/hooks/useGroupExpansion";
import { ChevronUpIcon, ChevronDownIcon } from "@heroicons/react/24/outline";

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
  alerts: AlertDto[];
  initialFacets: FacetDto[];
  alertsTotalCount: number;
  columns: ColumnDef<AlertDto>[];
  isAsyncLoading?: boolean;
  presetName: string;
  presetTabs?: PresetTab[];
  isRefreshAllowed?: boolean;
  isMenuColDisplayed?: boolean;
  facetsCel: string | null;
  facetsPanelRefreshToken: string | undefined;
  setDismissedModalAlert?: (alert: AlertDto[] | null) => void;
  mutateAlerts?: () => void;
  setRunWorkflowModalAlert?: (alert: AlertDto) => void;
  setDismissModalAlert?: (alert: AlertDto[] | null) => void;
  setChangeStatusAlert?: (alert: AlertDto) => void;
  onReload?: (query: AlertsQuery) => void;
  onQueryChange?: (query: AlertsTableDataQuery) => void;
}

export function AlertTableServerSide({
  alerts,
  alertsTotalCount,
  columns,
  initialFacets,
  isAsyncLoading = false,
  presetName,
  facetsCel,
  facetsPanelRefreshToken,
  isRefreshAllowed = true,
  setDismissedModalAlert,
  mutateAlerts,
  setRunWorkflowModalAlert,
  setDismissModalAlert,
  setChangeStatusAlert,
  onReload,
  onQueryChange,
}: Props) {
  const [clearFiltersToken, setClearFiltersToken] = useState<string | null>(
    null
  );
  const [grouping, setGrouping] = useState<GroupingState>([]);
  const [filterCel, setFilterCel] = useState<string | null>(null);
  const [searchCel, setSearchCel] = useState<string | null>(null);

  const alertsQueryRef = useRef<AlertsQuery | null>(null);
  const [rowStyle] = useAlertRowStyle();
  const [columnTimeFormats, setColumnTimeFormats] = useLocalStorage<
    Record<string, TimeFormatOption>
  >(`column-time-formats-${presetName}`, {});
  const a11yContainerRef = useRef<HTMLDivElement>(null);
  const { data: configData } = useConfig();
  const noisyAlertsEnabled = configData?.NOISY_ALERTS_ENABLED;
  const { theme } = useAlertTableTheme();
  const [timeFrame, setTimeFrame] = useTimeframeState({
    enableQueryParams: true,
    defaultTimeframe: {
      type: "all-time",
      isPaused: false,
    } as AllTimeFrame,
  });

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

  const [sorting, setSorting] = useState<SortingState>(
    noisyAlertsEnabled ? [{ id: "noise", desc: true }] : []
  );
  const [paginationState, setPaginationState] = useState<PaginationState>({
    limit: rowStyle == "relaxed" ? 20 : 50,
    offset: 0,
  });
  const paginationStateRef = useRef(paginationState);
  paginationStateRef.current = paginationState;

  const [, setViewedAlerts] = useLocalStorage<ViewedAlert[]>(
    `viewed-alerts-${presetName}`,
    []
  );
  const [lastViewedAlert, setLastViewedAlert] = useState<string | null>(null);

  useEffect(
    function whenQueryChange() {
      if (filterCel === null || searchCel === null || timeFrame === null) {
        return;
      }

      if (onQueryChange) {
        const query: AlertsTableDataQuery = {
          filterCel: filterCel,
          searchCel: searchCel,
          timeFrame: timeFrame,
          limit: paginationState.limit,
          offset: paginationState.offset,
          sortOptions: sorting.map((s) => ({
            sortBy: s.id,
            sortDirection: s.desc ? "DESC" : "ASC",
          })),
        };
        onQueryChange(query);
      }
    },
    [filterCel, searchCel, paginationState, sorting, timeFrame, onQueryChange]
  );

  const [selectedAlert, setSelectedAlert] = useState<AlertDto | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isIncidentSelectorOpen, setIsIncidentSelectorOpen] =
    useState<boolean>(false);

  const leftPinnedColumns = noisyAlertsEnabled
    ? ["severity", "checkbox", "status", "source", "noise"]
    : ["severity", "checkbox", "status", "source"];

  const isShiftPressed = useIsShiftKeyHeld();

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
    },
    meta: {
      columnTimeFormats: columnTimeFormats,
      setColumnTimeFormats: setColumnTimeFormats,
    },
    enableGrouping: true,
    manualSorting: true,
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
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
    onGroupingChange: setGrouping,
    isMultiSortEvent: () => isShiftPressed,
  });

  // When filterCel or searchCel changes, we need to reset pagination state offset to 0
  useEffect(
    () =>
      setPaginationState({
        ...paginationStateRef.current,
        offset: 0,
      }),
    [filterCel, searchCel, setPaginationState]
  );

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

    const selection = window.getSelection();
    if (selection && selection.toString().length > 0) {
      return; // Don't open sidebar if text is selected
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

  const facetsConfig: FacetsConfig = useMemo(() => {
    return {
      ["Severity"]: {
        canHitEmptyState: true,
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
        canHitEmptyState: true,
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
              src={`/icons/${facetOption.display_name}-icon.png`}
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

  // Add group expansion state
  const groupExpansionState = useGroupExpansion(true);
  const { toggleAll, areAllGroupsExpanded } = groupExpansionState;

  // Check if grouping is active
  const isGroupingActive = grouping.length > 0;

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
      <Table
        className="[&>table]:table-fixed [&>table]:w-full"
        data-testid="alerts-table"
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
        />
        <AlertsTableBody
          table={table}
          showSkeleton={showSkeleton}
          pageSize={paginationState.limit}
          theme={theme}
          lastViewedAlert={lastViewedAlert}
          onRowClick={handleRowClick}
          presetName={presetName}
          groupExpansionState={groupExpansionState}
        />
      </Table>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex-none">
        <div className="flex justify-between">
          <span data-testid="preset-page-title">
            <PageTitle className="capitalize inline">{presetName}</PageTitle>
          </span>
          <div className="grid grid-cols-[auto_auto] grid-rows-[auto_auto] gap-4">
            {timeFrame && (
              <EnhancedDateRangePickerV2
                timeFrame={timeFrame}
                setTimeFrame={setTimeFrame}
                hasPlay={true}
                hasRewind={false}
                hasForward={false}
                hasZoomOut={false}
                enableYearNavigation
              />
            )}

            <SettingsSelection table={table} presetName={presetName} />
          </div>
        </div>
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
          <div className="flex items-center justify-between w-full">
            <div className="flex-1">
              <AlertPresetManager
                presetName={presetName}
                onCelChanges={setSearchCel}
                table={table}
              />
            </div>
            
            {/* Add toggle button when grouping is active */}
            {isGroupingActive && (
              <Button
                size="sm"
                variant="secondary"
                onClick={toggleAll}
                icon={areAllGroupsExpanded() ? ChevronUpIcon : ChevronDownIcon}
                tooltip={areAllGroupsExpanded() ? "Collapse all groups" : "Expand all groups"}
                className="ml-2"
                color="orange"
              >
                {areAllGroupsExpanded() ? "Collapse All" : "Expand All"}
              </Button>
            )}
          </div>
        )}
      </div>

      <div className="pb-4">
        <div className="flex gap-4">
          {/* Facets sidebar */}
          <div className="w-33 min-w-[12rem] overflow-y-auto">
            <FacetsPanelServerSide
              usePropertyPathsSuggestions={true}
              entityName={"alerts"}
              facetOptionsCel={facetsCel}
              clearFiltersToken={clearFiltersToken}
              initialFacetsData={{ facets: initialFacets, facetOptions: null }}
              facetsConfig={facetsConfig}
              onCelChange={setFilterCel}
              revalidationToken={facetsPanelRefreshToken}
              isSilentReloading={isAsyncLoading}
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
              <Pagination
                totalCount={alertsTotalCount}
                isRefreshing={isAsyncLoading}
                isRefreshAllowed={isRefreshAllowed}
                state={paginationState}
                onStateChange={setPaginationState}
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
