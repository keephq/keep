import {
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  Icon,
  Callout,
} from "@tremor/react";
import { AlertsTableBody } from "./alerts-table-body";
import { AlertDto } from "./models";
import {
  CircleStackIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import { Provider } from "app/providers/providers";
import { User } from "app/settings/models";
import { User as NextUser } from "next-auth";
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
} from "@tanstack/react-table";
import PushPullBadge from "@/components/ui/push-pulled-badge/push-pulled-badge";
import moment from "moment";
import Image from "next/image";
import { Workflow } from "app/workflows/models";
import { useRouter } from "next/navigation";
import AlertName from "./alert-name";
import AlertAssignee from "./alert-assignee";
import AlertMenu from "./alert-menu";
import AlertSeverity from "./alert-severity";
import AlertExtraPayload, {
  getExtraPayloadNoKnownKeys,
} from "./alert-extra-payload";
import { useState } from "react";
import AlertColumnsSelect, {
  getColumnsOrderLocalStorageKey,
  getHiddenColumnsLocalStorageKey,
} from "./alert-columns-select";
import AlertTableCheckbox from "./alert-table-checkbox";
import { MAX_ALERTS_PER_WINDOW } from "utils/fatigue";
import AlertFatigueMeter from "./alert-fatigue-meter";
import AlertPagination from "./alert-pagination";
import { KeyedMutator } from "swr";

const getAlertLastReceieved = (lastRecievedFromAlert: Date) => {
  let lastReceived = "unknown";
  if (lastRecievedFromAlert) {
    lastReceived = lastRecievedFromAlert.toString();
    try {
      lastReceived = moment(lastRecievedFromAlert).fromNow();
    } catch {}
  }
  return (
    <span title={lastRecievedFromAlert.toISOString()}>{lastReceived}</span>
  );
};

const columnHelper = createColumnHelper<AlertDto>();

interface Props {
  alerts: AlertDto[];
  groupBy?: string;
  groupedByAlerts?: { [key: string]: AlertDto[] };
  workflows?: any[];
  providers?: Provider[];
  mutate?: KeyedMutator<AlertDto[]>;
  isAsyncLoading?: boolean;
  onDelete?: (
    fingerprint: string,
    lastReceived: Date,
    restore?: boolean
  ) => void;
  setAssignee?: (
    fingerprint: string,
    lastReceived: Date,
    unassign: boolean
  ) => void;
  users?: User[];
  currentUser: NextUser;
  openModal?: (alert: AlertDto) => void;
  presetName?: string;
  rowSelection?: RowSelectionState;
  setRowSelection?: OnChangeFn<RowSelectionState>;
  columnsToExclude?: string[];
  isHistoryOpen?: boolean;
}

export function AlertTable({
  alerts,
  groupedByAlerts = {},
  groupBy,
  workflows = [],
  providers = [],
  mutate,
  isAsyncLoading = false,
  onDelete,
  setAssignee,
  users = [],
  currentUser,
  openModal,
  presetName,
  rowSelection,
  setRowSelection,
  columnsToExclude = [],
  isHistoryOpen = false,
}: Props) {
  const router = useRouter();

  const handleWorkflowClick = (workflows: Workflow[]) => {
    if (workflows.length === 1) {
      router.push(`workflows/${workflows[0].id}`);
    } else {
      router.push("workflows");
    }
  };

  const checkboxColumn =
    rowSelection && !isHistoryOpen
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
      : [];

  const menuColumn = openModal
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
              canOpenHistory={
                !groupedByAlerts![(context.row.original as any)[groupBy!]]
              }
              openHistory={() => openModal!(context.row.original)}
              provider={providers.find(
                (p) => p.type === context.row.original.source![0]
              )}
              mutate={mutate ?? (async () => undefined)}
              callDelete={onDelete}
              setAssignee={setAssignee}
              currentUser={currentUser}
            />
          ),
        }),
      ]
    : [];

  const defaultColumns = [
    ...checkboxColumn,
    columnHelper.accessor("severity", {
      header: () => "Severity",
      cell: (context) => <AlertSeverity severity={context.getValue()} />,
    }),
    columnHelper.accessor("name", {
      header: () => "Name",
      cell: (context) => (
        <AlertName
          alert={context.row.original}
          workflows={workflows}
          handleWorkflowClick={handleWorkflowClick}
        />
      ),
    }),
    columnHelper.accessor("description", {
      header: () => "Description",
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
      cell: (context) => getAlertLastReceieved(context.getValue()),
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
    columnHelper.accessor("assignees", {
      header: "Assignee",
      cell: (context) => (
        <AlertAssignee
          assignee={
            (context.getValue() ?? {})[
              context.row.original.lastReceived?.toISOString()
            ]
          }
          users={users}
        />
      ),
    }),
    columnHelper.display({
      id: "fatigueMeter",
      header: () => (
        <div className="flex items-center gap-1">
          <span>Fatigue Meter</span>
          <Icon
            icon={QuestionMarkCircleIcon}
            tooltip={`Calculated based on the number of alerts / ${MAX_ALERTS_PER_WINDOW} in 1 hour`}
            variant="simple"
            color="gray"
          />
        </div>
      ),
      cell: ({ row }) => (
        <AlertFatigueMeter alerts={groupedByAlerts[row.original.fingerprint]} />
      ),
    }),
    columnHelper.display({
      id: "extraPayload",
      cell: (context) => <AlertExtraPayload alert={context.row.original} />,
    }),
    ...menuColumn,
  ];

  const extraPayloadKeys = Array.from(
    new Set(
      alerts
        .map((alert) => {
          const { extraPayload } = getExtraPayloadNoKnownKeys(alert);
          return Object.keys(extraPayload).concat(columnsToExclude);
        })
        .reduce((acc, keys) => [...acc, ...keys], [])
    )
  );
  // Create all the necessary columns
  const extraPayloadColumns = extraPayloadKeys.map((key) =>
    columnHelper.display({
      id: key,
      header: key,
      cell: (context) => {
        const val = (context.row.original as any)[key];
        if (typeof val === "object") {
          return JSON.stringify(val);
        }
        return (context.row.original as any)[key]?.toString() ?? "";
      },
    })
  );

  const columnsToHideFromLocalStorage = localStorage.getItem(
    getHiddenColumnsLocalStorageKey(presetName)
  );
  const columnOrderLocalStorage = localStorage.getItem(
    getColumnsOrderLocalStorageKey(presetName)
  );

  const columns = [...defaultColumns, ...extraPayloadColumns];
  const [columnOrder, setColumnOrder] = useState<ColumnOrderState>(
    columnOrderLocalStorage ? JSON.parse(columnOrderLocalStorage) : []
  );
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(
    // Defaultly exclude the extra payload columns from the default visibility
    !!columnsToHideFromLocalStorage
      ? JSON.parse(columnsToHideFromLocalStorage)
      : extraPayloadKeys.reduce((obj, key) => {
          obj[key] = false;
          return obj;
        }, {} as any)
  );
  const table = useReactTable({
    data: alerts,
    columns: columns,
    onColumnOrderChange: setColumnOrder,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    state: {
      columnVisibility,
      columnOrder,
      rowSelection,
    },
    onColumnVisibilityChange: setColumnVisibility,
    getRowId: (row) => row.fingerprint,
    enableRowSelection: true,
    pageCount: 10,
    onRowSelectionChange: setRowSelection,
  });

  return (
    <>
      {presetName && (
        <AlertColumnsSelect
          table={table}
          presetName={presetName}
          setColumnVisibility={setColumnVisibility}
          isLoading={isAsyncLoading}
          columnOrder={columnOrder}
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
                  className={`bg-white pb-0 ${
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
      <AlertPagination table={table} mutate={mutate} />
    </>
  );
}
