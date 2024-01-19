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
import Image from "next/image";
import AlertName from "./alert-name";
import AlertAssignee from "./alert-assignee";
import AlertMenu from "./alert-menu";
import AlertSeverity from "./alert-severity";
import AlertExtraPayload, {
  getExtraPayloadNoKnownKeys,
} from "./alert-extra-payload";
import { useEffect, useState } from "react";
import AlertColumnsSelect, {
  getColumnsOrderLocalStorageKey,
  getHiddenColumnsLocalStorageKey,
} from "./alert-columns-select";
import AlertTableCheckbox from "./alert-table-checkbox";
import { AlertHistory } from "./alert-history";
import AlertPagination from "./alert-pagination";
import { getAlertLastReceieved } from "utils/helpers";

const columnHelper = createColumnHelper<AlertDto>();

interface Props {
  alerts: AlertDto[];
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
  presetName?: string;
  rowSelection?: RowSelectionState;
  setRowSelection?: OnChangeFn<RowSelectionState>;
  columnsToExclude?: string[];
}

const getExtraPayloadKeys = (
  alerts: AlertDto[],
  columnsToExclude: string[]
) => {
  return Array.from(
    new Set(
      alerts
        .map((alert) => {
          const { extraPayload } = getExtraPayloadNoKnownKeys(alert);
          return Object.keys(extraPayload).concat(columnsToExclude);
        })
        .reduce((acc, keys) => [...acc, ...keys], [])
    )
  );
};

const getColumnsToHide = (
  presetName: string | undefined,
  extraPayloadKeys: string[]
): { [key: string]: boolean } => {
  const columnsToHideFromLocalStorage = localStorage.getItem(
    getHiddenColumnsLocalStorageKey(presetName)
  );
  return columnsToHideFromLocalStorage
    ? JSON.parse(columnsToHideFromLocalStorage)
    : extraPayloadKeys.reduce((obj, key) => {
        obj[key] = false;
        return obj;
      }, {} as { [key: string]: boolean });
};

export function AlertTable({
  alerts,
  isAsyncLoading = false,
  presetName,
  rowSelection,
  setRowSelection,
  columnsToExclude = [],
}: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<AlertDto | undefined>(
    undefined
  );
  const columnOrderLocalStorage = localStorage.getItem(
    getColumnsOrderLocalStorageKey(presetName)
  );

  const openModal = (alert: AlertDto) => {
    setSelectedAlert(alert);
    setIsOpen(true);
  };

  const enabledRowSelection =
    presetName === "Deleted" || (isOpen && !presetName)
      ? undefined
      : rowSelection;

  const checkboxColumn = enabledRowSelection
    ? [
        columnHelper.display({
          id: "checkbox",
          header: (context) => (
            <AlertTableCheckbox
              checked={context.table.getIsAllRowsSelected()}
              indeterminate={context.table.getIsSomeRowsSelected()}
              onChange={context.table.getToggleAllRowsSelectedHandler()}
              disabled={alerts.length === 0}
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

  const menuColumn = presetName
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
              openHistory={() => openModal(context.row.original)}
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
      cell: (context) => <AlertName alert={context.row.original} />,
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
    columnHelper.accessor("assignees", {
      header: "Assignee",
      cell: (context) => (
        <AlertAssignee
          assignee={
            (context.getValue() ?? {})[
              context.row.original.lastReceived?.toISOString()
            ]
          }
        />
      ),
    }),
    columnHelper.display({
      id: "extraPayload",
      header: "Extra Payload",
      cell: (context) => <AlertExtraPayload alert={context.row.original} />,
    }),
    ...menuColumn,
  ];

  const extraPayloadKeys = getExtraPayloadKeys(alerts, columnsToExclude);
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

  const columns = [...defaultColumns, ...extraPayloadColumns];
  const [columnOrder, setColumnOrder] = useState<ColumnOrderState>(
    columnOrderLocalStorage ? JSON.parse(columnOrderLocalStorage) : []
  );
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(
    // Defaultly exclude the extra payload columns from the default visibility
    getColumnsToHide(presetName, extraPayloadKeys)
  );

  useEffect(() => {
    const extraPayloadKeys = getExtraPayloadKeys(alerts, columnsToExclude);
    setColumnVisibility(getColumnsToHide(presetName, extraPayloadKeys));
  }, [alerts]);

  const table = useReactTable({
    data: alerts,
    columns: columns,
    onColumnOrderChange: setColumnOrder,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    state: {
      columnVisibility,
      columnOrder,
      rowSelection: enabledRowSelection,
    },
    initialState: {
      pagination: { pageSize: 10 },
    },
    onColumnVisibilityChange: setColumnVisibility,
    enableRowSelection: true,
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
      <AlertPagination
        table={table}
        // hide with history
      />
      {selectedAlert && (
        <AlertHistory
          isOpen={isOpen}
          selectedAlert={selectedAlert}
          closeModal={() => setIsOpen(false)}
        />
      )}
    </>
  );
}
