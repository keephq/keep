import { useState } from "react";
import {
  ColumnDef,
  FilterFn,
  RowSelectionState,
  VisibilityState,
  createColumnHelper,
} from "@tanstack/react-table";
import { AlertDto } from "./models";
import { Accordion, AccordionBody, AccordionHeader, Icon } from "@tremor/react";
import AlertTableCheckbox from "./alert-table-checkbox";
import AlertSeverity from "./alert-severity";
import AlertName from "./alert-name";
import { getAlertLastReceieved } from "utils/helpers";
import Image from "next/image";
import AlertAssignee from "./alert-assignee";
import AlertExtraPayload from "./alert-extra-payload";
import AlertMenu from "./alert-menu";
import { isSameDay, isValid, isWithinInterval, startOfDay } from "date-fns";
import { severityMapping } from "./models";
import {
  MdOutlineNotificationsActive,
  MdOutlineNotificationsOff,
} from "react-icons/md";

export const DEFAULT_COLS = [
  "noise",
  "checkbox",
  "severity",
  "name",
  "description",
  "status",
  "lastReceived",
  "source",
  "assignee",
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

const invertedSeverityMapping = Object.entries(severityMapping).reduce<{
  [key: string]: number;
}>((acc, [key, value]) => {
  acc[value as keyof typeof acc] = Number(key);
  return acc;
}, {});

const customSeveritySortFn = (rowA: any, rowB: any) => {
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
  setDismissModalAlert?: (alert: AlertDto[]) => void;
  setChangeStatusAlert?: (alert: AlertDto) => void;
  presetName: string;
  presetNoisy?: boolean;
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
    setChangeStatusAlert,
    presetName,
    presetNoisy = false,
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
        const keys = colName.split(".");
        let alertValue: any = context.row.original;
        for (const key of keys) {
          if (
            alertValue &&
            typeof alertValue === "object" &&
            key in alertValue
          ) {
            alertValue = alertValue[key as keyof typeof alertValue];
          } else {
            alertValue = undefined;
            break;
          }
        }

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
    // noisy column
    columnHelper.display({
      id: "noise",
      size: 5,
      header: () => <></>,
      cell: (context) => {
        // Get the status of the alert
        const status = context.row.original.status;
        const isNoisy = context.row.original.isNoisy;

        // Return null if presetNoisy is not true
        if (!presetNoisy && !isNoisy) {
          return null;
        } else if (presetNoisy) {
          // Decide which icon to display based on the status
          if (status === "firing") {
            return <Icon icon={MdOutlineNotificationsActive} color="red" />;
          } else {
            return <Icon icon={MdOutlineNotificationsOff} color="red" />;
          }
        }
        // else, noisy alert in non noisy preset
        else {
          if (status === "firing") {
            return <Icon icon={MdOutlineNotificationsActive} color="red" />;
          } else {
            return null;
          }
        }
      },
      enableSorting: false,
    }),
    ,
    ...(isCheckboxDisplayed
      ? [
          columnHelper.display({
            id: "checkbox",
            size: 10,
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
        (context.getValue() ?? []).map((source, index) => {
          let imagePath = `/icons/${source}-icon.png`;
          if (source.includes("@")) {
            imagePath = "/icons/mailgun-icon.png";
          }
          return (
            <Image
              className={`inline-block ${index == 0 ? "" : "-ml-2"}`}
              key={source}
              alt={source}
              height={24}
              width={24}
              title={source}
              src={imagePath}
            />
          );
        }),
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
                setChangeStatusAlert={setChangeStatusAlert}
              />
            ),
          }),
        ]
      : []) as ColumnDef<AlertDto>[]),
  ] as ColumnDef<AlertDto>[];
};
