import {
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  Icon,
  Callout,
} from "@tremor/react";
import { AlertsTableBody } from "./alerts-table-body";
import { AlertDto, AlertKnownKeys } from "./models";
import {
  CircleStackIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import {
  ColumnOrderState,
  OnChangeFn,
  RowSelectionState,
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
  VisibilityState,
  getPaginationRowModel,
  PaginationState,
  ColumnDef,
} from "@tanstack/react-table";
import PushPullBadge from "@/components/ui/push-pulled-badge/push-pulled-badge";
import Image from "next/image";
import AlertName from "./alert-name";
import AlertAssignee from "./alert-assignee";
import AlertSeverity from "./alert-severity";
import { useEffect, useState } from "react";
import AlertColumnsSelect, {
  getColumnsOrderLocalStorageKey,
  getHiddenColumnsLocalStorageKey,
} from "./alert-columns-select";
import AlertPagination from "./alert-pagination";
import { getAlertLastReceieved } from "utils/helpers";
import AlertTableCheckbox from "./alert-table-checkbox";
import AlertExtraPayload from "./alert-extra-payload";
import AlertMenu from "./alert-menu";
import { useRouter } from "next/navigation";

export const getDefaultColumnVisibility = (
  columnVisibilityState: VisibilityState = {},
  columnsToExclude: string[]
) => {
  const visibilityStateFromExcludedColumns =
    columnsToExclude.reduce<VisibilityState>(
      (acc, column) => ({ ...acc, [column]: false }),
      {}
    );

  return {
    ...columnVisibilityState,
    ...visibilityStateFromExcludedColumns,
  };
};

export const getColumnsOrder = (presetName?: string): ColumnOrderState => {
  if (presetName === undefined) {
    return [];
  }

  const columnOrderLocalStorage = localStorage.getItem(
    getColumnsOrderLocalStorageKey(presetName)
  );

  if (columnOrderLocalStorage) {
    return JSON.parse(columnOrderLocalStorage);
  }

  return [];
};

const hardcodedDefaultHidden = [
  "playbook_url",
  "ack_status",
  "deletedAt",
  "created_by",
  "assignees",
];

export const getHiddenColumns = (
  presetName?: string,
  columns?: ColumnDef<AlertDto>[]
): VisibilityState => {
  const defaultHidden =
    columns
      ?.filter((c) => c.id && !AlertKnownKeys.includes(c.id))
      .map((c) => c.id!) ?? [];
  if (presetName === undefined) {
    return getDefaultColumnVisibility({}, [
      ...hardcodedDefaultHidden,
      ...defaultHidden,
    ]);
  }

  const hiddenColumnsFromLocalStorage = localStorage.getItem(
    getHiddenColumnsLocalStorageKey(presetName)
  );

  if (hiddenColumnsFromLocalStorage) {
    return JSON.parse(hiddenColumnsFromLocalStorage);
  }

  return getDefaultColumnVisibility({}, [
    ...hardcodedDefaultHidden,
    ...defaultHidden,
  ]);
};

const getPaginatedData = (
  alerts: AlertDto[],
  { pageIndex, pageSize }: PaginationState
) => alerts.slice(pageIndex * pageSize, (pageIndex + 1) * pageSize);

const getDataPageCount = (dataLength: number, { pageSize }: PaginationState) =>
  Math.ceil(dataLength / pageSize);

export const columnHelper = createColumnHelper<AlertDto>();

interface UseAlertTableCols {
  additionalColsToGenerate?: string[];
  isCheckboxDisplayed?: boolean;
  isMenuDisplayed?: boolean;
}

export const useAlertTableCols = ({
  additionalColsToGenerate = [],
  isCheckboxDisplayed,
  isMenuDisplayed,
}: UseAlertTableCols = {}) => {
  const router = useRouter();
  const [expandedToggles, setExpandedToggles] = useState<RowSelectionState>({});
  const [noteModalOpen, setNoteModalOpen] = useState('');

  const filteredAndGeneratedCols = additionalColsToGenerate.map((colName) =>
    columnHelper.display({
      id: colName,
      header: colName,
      cell: (context) => {
        const alertValue = context.row.original[colName as keyof AlertDto];

        if (typeof alertValue === "object") {
          return JSON.stringify(alertValue);
        }

        if (alertValue) {
          return alertValue.toString();
        }

        return "";
      },
    })
  ) as ColumnDef<AlertDto>[];

  return [
    ...(isCheckboxDisplayed
      ? [
          columnHelper.display({
            id: "checkbox",
            header: (context) => (
              <AlertTableCheckbox
                checked={context.table.getIsAllRowsSelected()}
                indeterminate={context.table.getIsSomeRowsSelected()}
                onChange={context.table.getToggleAllRowsSelectedHandler()}
              />
            ),
            cell: (context) => (
              <AlertTableCheckbox
                checked={context.row.getIsSelected()}
                indeterminate={context.row.getIsSomeSelected()}
                onChange={context.row.getToggleSelectedHandler()}
              />
            ),
          }),
        ]
      : ([] as ColumnDef<AlertDto>[])),
    columnHelper.accessor("severity", {
      header: "Severity",
      cell: (context) => <AlertSeverity severity={context.getValue()} />,
    }),
    columnHelper.display({
      id: "name",
      header: "Name",
      cell: (context) => <AlertName alert={context.row.original}
                            isNoteModalOpen={noteModalOpen === context.row.original.fingerprint}
                            setNoteModalOpen={setNoteModalOpen}
      />,
    }),
    columnHelper.accessor("description", {
      header: "Description",
      cell: (context) => (
        <div
          className="max-w-[340px] flex items-center"
          title={context.getValue()}
        >
          <div className="truncate">{context.getValue()}</div>
        </div>
      ),
    }),
    columnHelper.accessor("pushed", {
      id: "pushed",
      header: () => (
        <div className="flex items-center gap-1">
          <span>Pushed</span>
          <Icon
            icon={QuestionMarkCircleIcon}
            tooltip="Whether the alert was pushed or pulled from the alert source"
            variant="simple"
            color="gray"
          />
        </div>
      ),
      cell: (context) => <PushPullBadge pushed={context.getValue()} />,
    }),
    columnHelper.accessor("status", {
      header: "Status",
    }),
    columnHelper.accessor("lastReceived", {
      header: "Last Received",
      cell: (context) => (
        <span title={context.getValue().toISOString()}>
          {getAlertLastReceieved(context.getValue())}
        </span>
      ),
    }),
    columnHelper.accessor("source", {
      header: "Source",
      cell: (context) =>
        (context.getValue() ?? []).map((source, index) => (
          <Image
            className={`inline-block ${index == 0 ? "" : "-ml-2"}`}
            key={source}
            alt={source}
            height={24}
            width={24}
            title={source}
            src={`/icons/${source}-icon.png`}
          />
        )),
    }),
    columnHelper.accessor("assignee", {
      header: "Assignee",
      cell: (context) => <AlertAssignee assignee={context.getValue()} />,
    }),
    columnHelper.display({
      id: "extraPayload",
      header: "Extra Payload",
      cell: (context) => (
        <AlertExtraPayload
          alert={context.row.original}
          isToggled={expandedToggles[context.row.original.id]}
          setIsToggled={(newValue) =>
            setExpandedToggles({
              ...expandedToggles,
              [context.row.original.id]: newValue,
            })
          }
        />
      ),
    }),
    ...filteredAndGeneratedCols,
    ...((isMenuDisplayed
      ? [
          columnHelper.display({
            id: "alertMenu",
            meta: {
              thClassName: "sticky right-0",
              tdClassName: "sticky right-0",
            },
            cell: (context) => (
              <AlertMenu
                alert={context.row.original}
                openHistory={() =>
                  router.replace(`/alerts?id=${context.row.original.id}`, {
                    scroll: false,
                  })
                }
              />
            ),
          }),
        ]
      : []) as ColumnDef<AlertDto>[]),
  ] as ColumnDef<AlertDto>[];
};

interface Props {
  alerts: AlertDto[];
  columns: ColumnDef<AlertDto>[];
  isAsyncLoading?: boolean;
  presetName?: string;
  columnsToExclude?: (keyof AlertDto)[];
  isMenuColDisplayed?: boolean;
  isRefreshAllowed?: boolean;
  rowSelection?: {
    state: RowSelectionState;
    onChange: OnChangeFn<RowSelectionState>;
  };
  rowPagination?: {
    state: PaginationState;
    onChange: OnChangeFn<PaginationState>;
  };
}

export function AlertTable({
  alerts,
  columns,
  isAsyncLoading = false,
  presetName,
  rowSelection,
  rowPagination,
  isRefreshAllowed = true,
  columnsToExclude = [],
}: Props) {
  const [columnOrder, setColumnOrder] = useState<ColumnOrderState>(
    getColumnsOrder(presetName)
  );
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(
    getHiddenColumns(presetName, columns)
  );

  useEffect(() => {
    setColumnVisibility(getHiddenColumns(presetName, columns));
  }, [presetName, columns]);

  const table = useReactTable({
    data: rowPagination
      ? getPaginatedData(alerts, rowPagination.state)
      : alerts,
    columns: columns,
    state: {
      columnVisibility: getDefaultColumnVisibility(
        columnVisibility,
        columnsToExclude
      ),
      columnOrder: columnOrder,
      rowSelection: rowSelection?.state,
      pagination: rowPagination?.state,
    },
    initialState: {
      pagination: { pageSize: 10 },
    },
    getCoreRowModel: getCoreRowModel(),
    pageCount: rowPagination
      ? getDataPageCount(alerts.length, rowPagination.state)
      : undefined,
    getPaginationRowModel: rowPagination ? undefined : getPaginationRowModel(),
    enableRowSelection: rowSelection !== undefined,
    manualPagination: rowPagination !== undefined,
    onPaginationChange: rowPagination?.onChange,
    onColumnOrderChange: setColumnOrder,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: rowSelection?.onChange,
  });

  return (
    <>
      {presetName && (
        <AlertColumnsSelect
          table={table}
          presetName={presetName}
          isLoading={isAsyncLoading}
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
      <Table>
        <TableHead>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHeaderCell
                  key={header.id}
                  className={`bg-white pb-0 capitalize ${
                    header.column.columnDef.meta?.thClassName
                      ? header.column.columnDef.meta?.thClassName
                      : ""
                  }`}
                >
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext()
                  )}
                </TableHeaderCell>
              ))}
            </TableRow>
          ))}
        </TableHead>
        <AlertsTableBody table={table} showSkeleton={isAsyncLoading} />
      </Table>
      <AlertPagination table={table} isRefreshAllowed={isRefreshAllowed} />
    </>
  );
}
