import {
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  Callout,
  AccordionBody,
  AccordionHeader,
  Accordion,
} from "@tremor/react";
import { AlertsTableBody } from "./alerts-table-body";
import { AlertDto, AlertKnownKeys } from "./models";
import { CircleStackIcon } from "@heroicons/react/24/outline";
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
  Header,
} from "@tanstack/react-table";
import Image from "next/image";
import AlertName from "./alert-name";
import AlertAssignee from "./alert-assignee";
import AlertSeverity from "./alert-severity";
import { useRef, useState } from "react";
import AlertPagination from "./alert-pagination";
import { getAlertLastReceieved } from "utils/helpers";
import AlertTableCheckbox from "./alert-table-checkbox";
import AlertExtraPayload from "./alert-extra-payload";
import AlertMenu from "./alert-menu";
import { useRouter } from "next/navigation";
import AlertColumnsSelect, {
  getHiddenColumnsLocalStorageKey,
} from "./alert-columns-select";
import {
  DragDropContext,
  Droppable,
  Draggable,
  DragUpdate,
} from "react-beautiful-dnd";

const getColumnsOrderLocalStorageKey = (presetName: string = "default") => {
  return `columnsOrder-${presetName}`;
};

export const staticColumns = ["checkbox", "alertMenu"];

export const toVisibilityState = (columnsToHide: string[]) => {
  return columnsToHide.reduce<VisibilityState>(
    (acc, column) => ({ ...acc, [column]: false }),
    {}
  );
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

export const getHiddenColumns = (
  columns: ColumnDef<AlertDto>[],
  presetName?: string
): VisibilityState => {
  const savedColumnsToShow = localStorage.getItem(
    getHiddenColumnsLocalStorageKey(presetName)
  );

  if (!savedColumnsToShow || !presetName) {
    return toVisibilityState(
      columns
        .filter(
          (c) =>
            c.id &&
            AlertKnownKeys.includes(c.id) === false &&
            staticColumns.includes(c.id) === false
        )
        .map((c) => c.id!) ?? []
    );
  }

  const columnsToShow = JSON.parse(savedColumnsToShow) as string[];
  return toVisibilityState(
    columns
      .filter((c) => c.id && columnsToShow.includes(c.id) === false)
      .map((c) => c.id!)
  );
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

export const jsonColumn = (jsonObject: object) => {
  return (
    <Accordion>
      <AccordionHeader>Value</AccordionHeader>
      <AccordionBody>
        <pre className="overflow-y-scroll">
          {JSON.stringify(jsonObject, null, 2)}
        </pre>
      </AccordionBody>
    </Accordion>
  );
};

export const useAlertTableCols = ({
  additionalColsToGenerate = [],
  isCheckboxDisplayed,
  isMenuDisplayed,
}: UseAlertTableCols = {}) => {
  const router = useRouter();
  const [expandedToggles, setExpandedToggles] = useState<RowSelectionState>({});

  const filteredAndGeneratedCols = additionalColsToGenerate.map((colName) =>
    columnHelper.display({
      id: colName,
      header: colName,
      cell: (context) => {
        const alertValue = context.row.original[colName as keyof AlertDto];

        if (typeof alertValue === "object" && alertValue !== null) {
          return jsonColumn(alertValue);
        }

        if (alertValue && alertValue !== null) {
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
      id: "severity",
      header: "Severity",
      cell: (context) => <AlertSeverity severity={context.getValue()} />,
    }),
    columnHelper.display({
      id: "name",
      header: "Name",
      cell: (context) => <AlertName alert={context.row.original} />,
    }),
    columnHelper.accessor("description", {
      id: "description",
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
    columnHelper.accessor("status", {
      id: "status",
      header: "Status",
    }),
    columnHelper.accessor("lastReceived", {
      id: "lastReceived",
      header: "Last Received",
      cell: (context) => (
        <span title={context.getValue().toISOString()}>
          {getAlertLastReceieved(context.getValue())}
        </span>
      ),
    }),
    columnHelper.accessor("source", {
      id: "source",
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
      id: "assignee",
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
}: Props) {
  const [columnOrder, setColumnOrder] = useState<ColumnOrderState>(
    getColumnsOrder(presetName)
  );

  const table = useReactTable({
    data: rowPagination
      ? getPaginatedData(alerts, rowPagination.state)
      : alerts,
    columns: columns,
    state: {
      columnVisibility: getHiddenColumns(columns, presetName),
      columnOrder: columnOrder,
      rowSelection: rowSelection?.state,
      pagination: rowPagination?.state,
      columnPinning: {
        left: ["checkbox"],
        right: ["alertMenu"],
      },
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
    onRowSelectionChange: rowSelection?.onChange,
    enableColumnPinning: true,
  });

  function AlertTableColumn({
    index,
    header,
  }: {
    index: number;
    header: Header<AlertDto, unknown>;
  }) {
    return (
      <Draggable
        key={header.id}
        draggableId={header.id}
        index={index}
        isDragDisabled={staticColumns.includes(header.id)}
      >
        {(provided) => {
          return (
            <TableHeaderCell
              className={
                staticColumns.includes(header.id) === false
                  ? `hover:bg-slate-100`
                  : ""
              }
              {...provided.draggableProps}
              {...provided.dragHandleProps}
              ref={provided.innerRef}
            >
              <div className="flex items-center">
                {flexRender(
                  header.column.columnDef.header,
                  header.getContext()
                )}
              </div>
            </TableHeaderCell>
          );
        }}
      </Draggable>
    );
  }

  const currentColOrder = useRef<string[]>();
  const onDragUpdate = (dragUpdateObj: DragUpdate) => {
    const colOrder = currentColOrder.current
      ? [...currentColOrder.current]
      : [];
    const sIndex = dragUpdateObj.source.index;
    const dIndex = dragUpdateObj.destination && dragUpdateObj.destination.index;
    if (typeof sIndex === "number" && typeof dIndex === "number") {
      colOrder.splice(sIndex, 1);
      colOrder.splice(dIndex, 0, dragUpdateObj.draggableId);
      setColumnOrder(colOrder);
      if (presetName)
        localStorage.setItem(
          getColumnsOrderLocalStorageKey(presetName),
          JSON.stringify(colOrder)
        );
    }
  };
  const onDragStart = () => {
    currentColOrder.current = table.getAllColumns().map((o) => o.id);
  };
  const onDragEnd = () => {};

  return (
    <>
      {presetName && (
        <AlertColumnsSelect
          presetName={presetName}
          table={table}
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
            <DragDropContext
              key={headerGroup.id}
              onDragStart={onDragStart}
              onDragUpdate={onDragUpdate}
              onDragEnd={onDragEnd}
            >
              <Droppable droppableId="droppable" direction="horizontal">
                {(droppableProvided) => (
                  <TableRow
                    key={headerGroup.id}
                    ref={droppableProvided.innerRef}
                  >
                    {headerGroup.headers.map((header, index) => (
                      <AlertTableColumn
                        key={index}
                        index={index}
                        header={header}
                      />
                    ))}
                  </TableRow>
                )}
              </Droppable>
            </DragDropContext>
          ))}
        </TableHead>
        <AlertsTableBody table={table} showSkeleton={isAsyncLoading} />
      </Table>
      <AlertPagination table={table} isRefreshAllowed={isRefreshAllowed} />
    </>
  );
}
