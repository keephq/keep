import { useState } from "react";
import {
  ColumnDef,
  PaginationState,
  RowSelectionState,
  VisibilityState,
  createColumnHelper,
} from "@tanstack/react-table";
import { AlertDto, AlertKnownKeys } from "./models";
import { Accordion, AccordionBody, AccordionHeader } from "@tremor/react";
import AlertTableCheckbox from "./alert-table-checkbox";
import AlertSeverity from "./alert-severity";
import AlertName from "./alert-name";
import { getAlertLastReceieved } from "utils/helpers";
import Image from "next/image";
import AlertAssignee from "./alert-assignee";
import AlertExtraPayload from "./alert-extra-payload";
import AlertMenu from "./alert-menu";

const DEFAULT_COLS = [...AlertKnownKeys];

export const getPaginatedData = (
  alerts: AlertDto[],
  { pageIndex, pageSize }: PaginationState
) => alerts.slice(pageIndex * pageSize, (pageIndex + 1) * pageSize);

export const getDataPageCount = (
  dataLength: number,
  { pageSize }: PaginationState
) => Math.ceil(dataLength / pageSize);

export const getColumnsIds = (columns: ColumnDef<AlertDto>[]) =>
  columns.map((column) => column.id as string);

export const getDefaultColumnVisibilityState = (columnsIds: string[]) => {
  return columnsIds.reduce<VisibilityState>(
    (defaultColVisibState, columnId) => {
      if (DEFAULT_COLS.includes(columnId)) {
        return defaultColVisibState;
      }

      return { ...defaultColVisibState, [columnId]: false };
    },
    {}
  );
};

export const getOnlyVisibleCols = (
  columnVisibility: VisibilityState,
  columnsIds: string[]
): VisibilityState =>
  columnsIds.reduce<VisibilityState>((acc, columnId) => {
    if (DEFAULT_COLS.includes(columnId)) {
      return acc;
    }

    if (columnId in columnVisibility) {
      return { ...acc, [columnId]: columnVisibility[columnId] };
    }

    return { ...acc, [columnId]: false };
  }, columnVisibility);

const columnHelper = createColumnHelper<AlertDto>();

interface GenerateAlertTableColsArg {
  additionalColsToGenerate?: string[];
  isCheckboxDisplayed?: boolean;
  isMenuDisplayed?: boolean;
  setNoteModalAlert?: (alert: AlertDto) => void;
  setTicketModalAlert?: (alert: AlertDto) => void;
}

export const useAlertTableCols = ({
  additionalColsToGenerate = [],
  isCheckboxDisplayed,
  isMenuDisplayed,
  setNoteModalAlert,
  setTicketModalAlert,
}: GenerateAlertTableColsArg = {}) => {
  const [expandedToggles, setExpandedToggles] = useState<RowSelectionState>({});
  const [currentOpenMenu, setCurrentOpenMenu] = useState("");

  const filteredAndGeneratedCols = additionalColsToGenerate.map((colName) =>
    columnHelper.display({
      id: colName,
      header: colName,
      cell: (context) => {
        const alertValue = context.row.original[colName as keyof AlertDto];

        if (typeof alertValue === "object" && alertValue !== null) {
          return (
            <Accordion>
              <AccordionHeader>Value</AccordionHeader>
              <AccordionBody>
                <pre className="overflow-scroll max-w-lg">
                  {JSON.stringify(alertValue, null, 2)}
                </pre>
              </AccordionBody>
            </Accordion>
          );
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
      cell: (context) => (
        <AlertName
          alert={context.row.original}
          setNoteModalAlert={setNoteModalAlert}
          setTicketModalAlert={setTicketModalAlert}
        />
      ),
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
          isToggled={expandedToggles[context.row.original.fingerprint]}
          setIsToggled={(newValue) =>
            setExpandedToggles({
              ...expandedToggles,
              [context.row.original.fingerprint]: newValue,
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
                isMenuOpen={
                  context.row.original.fingerprint === currentOpenMenu
                }
                setIsMenuOpen={setCurrentOpenMenu}
              />
            ),
          }),
        ]
      : []) as ColumnDef<AlertDto>[]),
  ] as ColumnDef<AlertDto>[];
};
