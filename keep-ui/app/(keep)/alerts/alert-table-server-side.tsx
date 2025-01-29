import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Table, Card } from "@tremor/react";
import { AlertsTableBody } from "./alerts-table-body";
import { AlertDto } from "@/entities/alerts/model";
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
import { AlertPresetManager } from "./alert-preset-manager";
import { evalWithContext } from "./alerts-rules-builder";
import { TitleAndFilters } from "./TitleAndFilters";
import { severityMapping } from "@/entities/alerts/model";
import AlertTabs from "./alert-tabs";
import AlertSidebar from "./alert-sidebar";
import { AlertFacets } from "./alert-table-alert-facets";
import { DynamicFacet, FacetFilters } from "./alert-table-facet-types";
import { useConfig } from "@/utils/hooks/useConfig";
import { FacetsPanelServerSide } from "@/features/filter/facet-panel-server-side";
import Image from "next/image";
import { SeverityBorderIcon, UISeverity } from "@/shared/ui";
import { useUser } from "@/entities/users/model/useUser";
import { UserStatefulAvatar } from "@/entities/users/ui";
import { getStatusIcon, getStatusColor } from "@/shared/lib/status-utils";
import { Icon } from "@tremor/react";
import { BellIcon, BellSlashIcon } from "@heroicons/react/24/outline";
import AlertPaginationServerSide from "./alert-pagination-server-side";
import { FacetDto } from "@/features/filter";

const AssigneeLabel = ({ email }: { email: string }) => {
  const user = useUser(email);
  return user ? user.name : email;
};

export interface AlertsQuery {
  cel: string;
  pageIndex: number;
  offset: number;
  limit: number;
  sortBy: string;
  sortDirection: 'ASC' | 'DESC';
}

interface PresetTab {
  name: string;
  filter: string;
  id?: string;
}
interface Props {
  refreshToken: string | null;
  alerts: AlertDto[];
  initalFacets: FacetDto[];
  alertsTotalCount: number;
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
  onQueryChange?: (query:AlertsQuery) => void;
  onRefresh?: () => void;
}

export function AlertTableServerSide({
  refreshToken,
  alerts,
  alertsTotalCount,
  columns,
  initalFacets,
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
  onQueryChange,
  onRefresh
}: Props) {
  const [clearFiltersToken, setClearFiltersToken] = useState<string | null>(null);
  const [filterCel, setFilterCel] = useState<string>("");
  const [searchCel, setSearchCel] = useState<string>("");
  
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
    pageSize: 20,
  });

  const alertsQuery = useMemo(function whenQueryChange() {
    const resultCel = [searchCel, filterCel].filter(Boolean).join(' && ');
    const limit = paginationState.pageSize;
    const offset = limit * paginationState.pageIndex;
    const alertsQuery: AlertsQuery = {
      cel: resultCel, pageIndex: paginationState.pageIndex, offset, limit,
      sortBy: sorting[0]?.id,
      sortDirection: sorting[0]?.desc ? 'DESC' : 'ASC'
    }

    return alertsQuery;
  }, [filterCel, searchCel, paginationState, sorting]);

  useEffect(() => onQueryChange && onQueryChange(alertsQuery), [alertsQuery, onQueryChange])

  useEffect(function whenQueryChange() {
    const resultCel = [searchCel, filterCel].filter(Boolean).join(' && ');
    const limit = paginationState.pageSize;
    const offset = limit * paginationState.pageIndex;
    const alertsQuery: AlertsQuery = {
      cel: resultCel, pageIndex: paginationState.pageIndex, offset, limit,
      sortBy: sorting[0]?.id,
      sortDirection: sorting[0]?.desc ? 'DESC' : 'ASC'
    }

    onQueryChange && onQueryChange(alertsQuery);
  }, [filterCel, searchCel, paginationState, sorting, onQueryChange]);

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

  const leftPinnedColumns = noisyAlertsEnabled
    ? ["severity", "checkbox", "noise"]
    : ["severity", "checkbox"];

  const table = useReactTable({
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
      pagination: {
        pageIndex: paginationState.pageIndex,
        pageSize: paginationState.pageSize,
      }
    },
    manualSorting: true,
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
    manualPagination: true,
    pageCount: Math.ceil(alertsTotalCount / paginationState.pageSize),
    onPaginationChange: setPaginationState
  });

  const selectedRowIds = Object.entries(
    table.getSelectedRowModel().rowsById
  ).reduce<string[]>((acc, [alertId]) => {
    return acc.concat(alertId);
  }, []);

  let showSkeleton = isAsyncLoading;
  let showEmptyState =
    !!alertsQuery.cel && table.getPageCount() === 0 && !isAsyncLoading;

  useEffect(() => console.log({ isAsyncLoading }), [isAsyncLoading])

  const handleRowClick = (alert: AlertDto) => {
    // if presetName is alert-history, do not open sidebar
    if (presetName === "alert-history") {
      return;
    }
    setSelectedAlert(alert);
    setIsSidebarOpen(true);
  };

  const renderFacetOptionIcon = useCallback(
    (facetName: string, facetOptionName: string) => {
      facetName = facetName.toLowerCase();

      if (facetName === "source") {
        if (facetOptionName === "None") {
          return;
        }

        return (
          <Image
            className="inline-block"
            alt={facetOptionName}
            height={16}
            width={16}
            title={facetOptionName}
            src={
              facetOptionName.includes("@")
                ? "/icons/mailgun-icon.png"
                : `/icons/${facetOptionName}-icon.png`
            }
          />
        );
      }
      if (facetName === "severity") {
        return <SeverityBorderIcon severity={(severityMapping[Number(facetOptionName)] || facetOptionName) as UISeverity} />;
      }
      if (facetName === "assignee") {
        return <UserStatefulAvatar email={facetOptionName} size="xs" />;
      }
      if (facetName === "status") {
        return (
          <Icon
            icon={getStatusIcon(facetOptionName)}
            size="sm"
            color={getStatusColor(facetOptionName)}
            className="!p-0"
          />
        );
      }
      if (facetName === "dismissed") {
        return (
          <Icon
            icon={facetOptionName === "true" ? BellSlashIcon : BellIcon}
            size="sm"
            className="text-gray-600 !p-0"
          />
        );
      }

      return undefined;
    },
    []
  );

  const renderFacetOptionLabel = useCallback(
    (facetName: string, facetOptionName: string) => {
      facetName = facetName.toLowerCase();
      
      switch (facetName) {
        case "assignee":
          if (!facetOptionName) {
            return "Not assigned";
          }
          return <AssigneeLabel email={facetOptionName} />;
        case "dismissed":
          return facetOptionName === "true" ? "Dismissed" : "Not dismissed";
        case "severity": {
            const label = severityMapping[Number(facetOptionName)] || facetOptionName;
            return <span className="capitalize">{label}</span>;
        }
        default:
          return <span className="capitalize">{facetOptionName}</span>;
      }
    },
    []
  );

  return (
    // Add h-screen to make it full height and remove the default flex-col gap
    <div className="h-screen flex flex-col gap-4">
      {/* Add padding to account for any top nav/header */}
      <div className="px-4 flex-none">
        <TitleAndFilters
          table={table}
          alerts={alerts}
          presetName={presetName}
          onThemeChange={handleThemeChange}
        />
      </div>

      {/* Make actions/presets section fixed height */}
      <div className="h-14 px-4 flex-none">
        {selectedRowIds.length ? (
          <AlertActions
            selectedRowIds={selectedRowIds}
            alerts={alerts}
            table={table}
            clearRowSelection={table.resetRowSelection}
            setDismissModalAlert={setDismissedModalAlert}
            mutateAlerts={mutateAlerts}
            setIsIncidentSelectorOpen={setIsIncidentSelectorOpen}
            isIncidentSelectorOpen={isIncidentSelectorOpen}
          />
        ) : (
          <AlertPresetManager presetName={presetName} onCelChanges={(searchCel) => setSearchCel(searchCel)} />
        )}
      </div>

      {/* Main content area - uses flex-grow to fill remaining space */}
      <div className="flex-grow px-4 pb-4">
        <div className="h-full flex gap-6">
          {/* Facets sidebar */}
          <div className="w-33 min-w-[12rem] overflow-y-auto">
            <FacetsPanelServerSide
              key={searchCel}
              entityName={"alerts"}
              facetOptionsCel={searchCel}
              clearFiltersToken={clearFiltersToken}
              initialFacetsData={{ facets: initalFacets, facetOptions: null }}
              onCelChange={(cel) => setFilterCel(cel)}
              renderFacetOptionIcon={renderFacetOptionIcon}
              renderFacetOptionLabel={renderFacetOptionLabel}
              revalidationToken={refreshToken}
            />
          </div>

          {/* Table section */}
          <div className="flex-1 flex flex-col min-w-0">
            <Card className="h-full flex flex-col p-0 overflow-x-auto">
              <div className="flex-grow flex flex-col">
                {!presetStatic && (
                  <div className="flex-none">
                    <AlertTabs
                      presetId={presetId}
                      tabs={tabs}
                      setTabs={setTabs}
                      selectedTab={selectedTab}
                      setSelectedTab={setSelectedTab}
                    />
                  </div>
                )}

                <div ref={a11yContainerRef} className="sr-only" />

                {/* Make table wrapper scrollable */}
                <div className="flex-grow">
                  <Table className="[&>table]:table-fixed [&>table]:w-full">
                    <AlertsTableHeaders
                      columns={columns}
                      table={table}
                      presetName={presetName}
                      a11yContainerRef={a11yContainerRef}
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
              </div>
            </Card>
          </div>
        </div>
      </div>

      {/* Pagination footer - fixed height */}
      <div className="h-16 px-4 flex-none pl-[14rem]">
        <AlertPaginationServerSide
          table={table}
          isRefreshing={isAsyncLoading}
          isRefreshAllowed={isRefreshAllowed}
          onRefresh={() => onRefresh && onRefresh()}
        />
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
