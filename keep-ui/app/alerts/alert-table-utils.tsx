import { useState } from "react";
import {
  ColumnDef,
  FilterFn,
  Row,
  RowSelectionState,
  VisibilityState,
  createColumnHelper,
} from "@tanstack/react-table";
import { AlertDto } from "./models";
import { Accordion, AccordionBody, AccordionHeader } from "@tremor/react";
import AlertTableCheckbox from "./alert-table-checkbox";
import AlertSeverity from "./alert-severity";
import AlertName from "./alert-name";
import { getAlertLastReceieved } from "utils/helpers";
import Image from "next/image";
import AlertAssignee from "./alert-assignee";
import AlertExtraPayload from "./alert-extra-payload";
import AlertMenu from "./alert-menu";
import { isSameDay, isValid, isWithinInterval, startOfDay } from "date-fns";
import { Severity, severityMapping } from "./models";

export const DEFAULT_COLS = [
  "checkbox",
  "severity",
  "name",
  "description",
  "status",
  "lastReceived",
  "source",
  "assignee",
  "extraPayload",
  "alertMenu",
];
export const DEFAULT_COLS_VISIBILITY = DEFAULT_COLS.reduce<VisibilityState>(
  (acc, colId) => ({ ...acc, [colId]: true }),
  {}
);

export const getColumnsIds = (columns: ColumnDef<AlertDto>[]) =>
  columns.map((column) => column.id as keyof AlertDto);

export const getOnlyVisibleCols = (
  columnVisibility: VisibilityState,
  columnsIds: (keyof AlertDto)[]
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

export const isDateWithinRange: FilterFn<AlertDto> = (row, columnId, value) => {
  const date = new Date(row.getValue(columnId));

  const { start, end } = value;

  if (!date) {
    return true;
  }

  if (isValid(start) && isValid(end)) {
    return isWithinInterval(startOfDay(date), { start, end });
  }

  if (isValid(start)) {
    return isSameDay(start, date);
  }

  if (isValid(end)) {
    return isSameDay(end, date);
  }

  return true;
};

const columnHelper = createColumnHelper<AlertDto>();

const invertedSeverityMapping = Object.entries(severityMapping).reduce((acc, [key, value]) => {
  acc[value] = Number(key);
  return acc;
}, {});

const customSeveritySortFn = (rowA, rowB) => {
  // Assuming rowA and rowB contain the data in a property (like 'original' or directly)
  // Adjust the way to access severity values according to your data structure
  const severityValueA = rowA.original?.severity; // or rowA.severity;
  const severityValueB = rowB.original?.severity; // or rowB.severity;

  // Use the inverted mapping to get ranks
  const rankA = invertedSeverityMapping[severityValueA] || 0;
  const rankB = invertedSeverityMapping[severityValueB] || 0;

  return rankA > rankB ? 1 : rankA < rankB ? -1 : 0;
};
interface GenerateAlertTableColsArg {
  additionalColsToGenerate?: string[];
  isCheckboxDisplayed?: boolean;
  isMenuDisplayed?: boolean;
  setNoteModalAlert?: (alert: AlertDto) => void;
  setTicketModalAlert?: (alert: AlertDto) => void;
  setRunWorkflowModalAlert?: (alert: AlertDto) => void;
  setDismissModalAlert?: (alert: AlertDto) => void;
  presetName: string;
  setViewAlertModal?: (alert: AlertDto) => void;
}

export const useAlertTableCols = (
  {
    additionalColsToGenerate = [],
    isCheckboxDisplayed,
    isMenuDisplayed,
    setNoteModalAlert,
    setTicketModalAlert,
    setRunWorkflowModalAlert,
    setDismissModalAlert,
    presetName,
    setViewAlertModal,
  }: GenerateAlertTableColsArg = { presetName: "feed" }
) => {
  const [expandedToggles, setExpandedToggles] = useState<RowSelectionState>({});
  const [currentOpenMenu, setCurrentOpenMenu] = useState("");

  const filteredAndGeneratedCols = additionalColsToGenerate.map((colName) =>
    columnHelper.display({
      id: colName,
      header: colName,
      minSize: 100,
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
          return <div className="truncate">{alertValue.toString()}</div>;
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
            size: 50,
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
      minSize: 100,
      cell: (context) => <AlertSeverity severity={context.getValue()} />,
      sortingFn: customSeveritySortFn,

    }),
    columnHelper.display({
      id: "name",
      header: "Name",
      minSize: 330,
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
      minSize: 100,
      cell: (context) => (
        <div title={context.getValue()}>
          <div className="truncate">{context.getValue()}</div>
        </div>
      ),
    }),
    columnHelper.accessor("status", {
      id: "status",
      minSize: 100,
      header: "Status",
    }),
    columnHelper.accessor("lastReceived", {
      id: "lastReceived",
      header: "Last Received",
      filterFn: isDateWithinRange,
      minSize: 100,
      cell: (context) => (
        <span title={context.getValue().toISOString()}>
          {getAlertLastReceieved(context.getValue())}
        </span>
      ),
    }),
    columnHelper.accessor("source", {
      id: "source",
      header: "Source",
      minSize: 100,
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
      minSize: 100,
      cell: (context) => <AlertAssignee assignee={context.getValue()} />,
    }),
    columnHelper.display({
      id: "extraPayload",
      header: "Extra Payload",
      minSize: 200,
      cell: (context) => (
        <AlertExtraPayload
          alert={context.row.original}
          isToggled={
            // When menu is not displayed, it means we're in History mode and therefore
            // we need to use the alert id as the key to keep the state of the toggles and not the fingerprint
            // because all fingerprints are the same. (it's the history of that fingerprint :P)
            isMenuDisplayed
              ? expandedToggles[context.row.original.fingerprint]
              : expandedToggles[context.row.id]
          }
          setIsToggled={(newValue) =>
            setExpandedToggles({
              ...expandedToggles,
              [isMenuDisplayed
                ? context.row.original.fingerprint
                : context.row.id]: newValue,
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
              tdClassName: "sticky right-0",
            },
            size: 50,
            cell: (context) => (
              <AlertMenu
                presetName={presetName.toLowerCase()}
                alert={context.row.original}
                isMenuOpen={
                  context.row.original.fingerprint === currentOpenMenu
                }
                setIsMenuOpen={setCurrentOpenMenu}
                setRunWorkflowModalAlert={setRunWorkflowModalAlert}
                setDismissModalAlert={setDismissModalAlert}
                setViewAlertModal={setViewAlertModal}
              />
            ),
          }),
        ]
      : []) as ColumnDef<AlertDto>[]),
  ] as ColumnDef<AlertDto>[];
};
