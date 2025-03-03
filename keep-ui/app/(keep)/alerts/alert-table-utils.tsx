import { useState } from "react";
import {
  ColumnDef,
  FilterFn,
  RowSelectionState,
  VisibilityState,
  createColumnHelper,
} from "@tanstack/react-table";
import { AlertDto } from "@/entities/alerts/model";
import { Accordion, AccordionBody, AccordionHeader, Icon } from "@tremor/react";
import { AlertName } from "@/entities/alerts/ui";
import AlertAssignee from "./alert-assignee";
import AlertExtraPayload from "./alert-extra-payload";
import AlertMenu from "./alert-menu";
import { isSameDay, isValid, isWithinInterval } from "date-fns";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import {
  MdOutlineNotificationsActive,
  MdOutlineNotificationsOff,
} from "react-icons/md";
import { getStatusIcon, getStatusColor } from "@/shared/lib/status-utils";
import { useConfig } from "utils/hooks/useConfig";
import {
  TableIndeterminateCheckbox,
  TableSeverityCell,
  UISeverity,
} from "@/shared/ui";
import { DynamicImageProviderIcon } from "@/components/ui";
import clsx from "clsx";
import { RowStyle } from "./RowStyleSelection";
import {
  formatDateTime,
  TimeFormatOption,
  isDateTimeColumn,
} from "./alert-table-time-format";

export const DEFAULT_COLS = [
  "severity",
  "checkbox",
  "noise",
  "source",
  "name",
  "description",
  "status",
  "lastReceived",
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
    return isWithinInterval(date, { start, end });
  }

  if (isValid(start)) {
    return isSameDay(start, date);
  }

  if (isValid(end)) {
    return isSameDay(end, date);
  }

  return true;
};

/**
 * Utility function to get consistent row class names across all table components
 */
export const getRowClassName = (
  row: any,
  theme: Record<string, string>,
  lastViewedAlert: string | null,
  rowStyle: RowStyle
) => {
  const severity = row.original.severity || "info";
  const rowBgColor = theme[severity] || "bg-white";
  const isLastViewed = row.original.fingerprint === lastViewedAlert;

  return clsx(
    "cursor-pointer group",
    isLastViewed ? "bg-orange-50" : rowBgColor,
    rowStyle === "dense" ? "h-8" : "h-12",
    rowStyle === "dense" ? "[&>td]:py-1" : "[&>td]:py-3",
    "hover:bg-orange-100"
  );
};

/**
 * Utility function to get consistent cell class names
 */
export const getCellClassName = (
  cell: any,
  className: string,
  rowStyle: RowStyle,
  isLastViewed: boolean
) => {
  const isNameCell = cell.column.id === "name";

  return clsx(
    cell.column.columnDef.meta?.tdClassName,
    className,
    isNameCell && "name-cell",
    // For dense rows, make sure name cells don't expand too much
    rowStyle === "dense" && isNameCell && "w-auto max-w-2xl",
    "group-hover:bg-orange-100", // Group hover styling
    isLastViewed && "bg-orange-50" // Override with highlight if this is the last viewed row
  );
};

const columnHelper = createColumnHelper<AlertDto>();

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
  const [rowStyle] = useLocalStorage("alert-table-row-style", "default");
  const [columnTimeFormats] = useLocalStorage<Record<string, TimeFormatOption>>(
    `column-time-formats-${presetName}`,
    {}
  );
  const { data: configData } = useConfig();
  // check if noisy alerts are enabled
  const noisyAlertsEnabled = configData?.NOISY_ALERTS_ENABLED;

  const filteredAndGeneratedCols = additionalColsToGenerate.map((colName) =>
    columnHelper.accessor(
      (row) => {
        // Extract value using the dot notation path
        const keys = colName.split(".");
        let value: any = row;
        for (const key of keys) {
          if (value && typeof value === "object" && key in value) {
            value = value[key as keyof typeof value];
          } else {
            value = undefined;
            break;
          }
        }
        return value;
      },
      {
        id: colName,
        header: colName,
        minSize: 100,
        enableGrouping: true,
        getGroupingValue: (row) => {
          const keys = colName.split(".");
          let value: any = row;
          for (const key of keys) {
            if (value && typeof value === "object" && key in value) {
              value = value[key as keyof typeof value];
            } else {
              value = undefined;
              break;
            }
          }

          if (typeof value === "object" && value !== null) {
            return "object"; // Group all objects together
          }
          return value;
        },
        aggregatedCell: ({ getValue }) => {
          const value = getValue();
          if (typeof value === "object" && value !== null) {
            return "Multiple Objects";
          }
          return `${String(value ?? "N/A")}`;
        },
        cell: (context) => {
          const value = context.getValue();

          if (typeof value === "object" && value !== null) {
            return (
              <Accordion>
                <AccordionHeader>Value</AccordionHeader>
                <AccordionBody>
                  <pre className="overflow-scroll max-w-lg">
                    {JSON.stringify(value, null, 2)}
                  </pre>
                </AccordionBody>
              </Accordion>
            );
          }
          let isDateColumn = isDateTimeColumn(context.column.id);
          if (isDateColumn) {
            const date =
              value instanceof Date
                ? value
                : new Date(value as string | number);
            const isoString = date.toISOString();
            // Get the format from column format settings or use default
            const formatOption =
              columnTimeFormats[context.column.id] || "timeago";
            return (
              <span title={isoString}>
                {formatDateTime(date, formatOption)}
              </span>
            );
          }

          if (value) {
            return (
              <div
                className={clsx(
                  "truncate whitespace-pre-wrap",
                  rowStyle === "dense" ? "line-clamp-1" : "line-clamp-3"
                )}
              >
                {value.toString()}
              </div>
            );
          }

          return "";
        },
      }
    )
  ) as ColumnDef<AlertDto>[];

  return [
    columnHelper.display({
      id: "severity",
      maxSize: 2,
      header: () => <></>,
      cell: (context) => (
        <TableSeverityCell
          severity={context.row.original.severity as unknown as UISeverity}
        />
      ),
      meta: {
        tdClassName: "w-1 !p-0",
        thClassName: "w-1 !p-0",
      },
    }),
    ...(isCheckboxDisplayed
      ? [
          columnHelper.display({
            id: "checkbox",
            maxSize: 16,
            minSize: 16,
            meta: {
              tdClassName: "w-6 !py-2 !pl-2 !pr-1",
              thClassName: "w-6 !py-2 !pl-2 !pr-1 ",
            },
            header: (context) => (
              <TableIndeterminateCheckbox
                checked={context.table.getIsAllRowsSelected()}
                indeterminate={context.table.getIsSomeRowsSelected()}
                onChange={context.table.getToggleAllRowsSelectedHandler()}
              />
            ),
            cell: (context) => (
              <TableIndeterminateCheckbox
                checked={context.row.getIsSelected()}
                indeterminate={context.row.getIsSomeSelected()}
                onChange={context.row.getToggleSelectedHandler()}
              />
            ),
          }),
        ]
      : ([] as ColumnDef<AlertDto>[])),
    // noisy column
    ...(noisyAlertsEnabled
      ? [
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
                  return (
                    <Icon icon={MdOutlineNotificationsActive} color="red" />
                  );
                } else {
                  return <Icon icon={MdOutlineNotificationsOff} color="red" />;
                }
              }
              // else, noisy alert in non noisy preset
              else {
                if (status === "firing") {
                  return (
                    <Icon icon={MdOutlineNotificationsActive} color="red" />
                  );
                } else {
                  return null;
                }
              }
            },
            meta: {
              tdClassName: "p-0",
              thClassName: "p-0",
            },
            enableSorting: false,
          }),
        ]
      : []),
    // Source column with exact 40px width ( see alert-table-headers )
    columnHelper.accessor("source", {
      id: "source",
      header: () => <></>,
      minSize: 20,
      maxSize: 20,
      enableSorting: false,
      enableGrouping: true,
      getGroupingValue: (row) => row.source,
      enableResizing: false,
      cell: (context) => (
        <div className="flex items-center justify-center">
          {(context.getValue() ?? []).map((source, index) => {
            let imagePath = `/icons/${source}-icon.png`;
            if (source.includes("@")) {
              imagePath = "/icons/mailgun-icon.png";
            }
            return (
              <DynamicImageProviderIcon
                className={`inline-block ${index == 0 ? "" : "-ml-2"}`}
                key={source}
                alt={source}
                height={24}
                width={24}
                title={source}
                src={imagePath}
              />
            );
          })}
        </div>
      ),
      meta: {
        tdClassName: "!p-0 w-4 sm:w-8 !box-border",
        thClassName: "!p-0 w-4 sm:w-8 !box-border",
      },
    }),
    // Name column butted up against source
    columnHelper.accessor("name", {
      id: "name",
      header: "Name",
      enableGrouping: true,
      enableResizing: true,
      getGroupingValue: (row) => row.name,
      cell: (context) => (
        <div className="w-full">
          <AlertName alert={context.row.original} className="flex-grow" />
        </div>
      ),
      meta: {
        tdClassName: "!pl-0 w-full",
        thClassName: "!pl-1 w-full",
      },
    }),
    columnHelper.accessor("description", {
      id: "description",
      header: "Description",
      enableGrouping: true,
      minSize: 100,
      cell: (context) => (
        <div title={context.getValue()}>
          <div
            className={clsx(
              "whitespace-pre-wrap",
              rowStyle === "dense"
                ? "truncate line-clamp-1"
                : "truncate line-clamp-3"
            )}
          >
            {context.getValue()}
          </div>
        </div>
      ),
    }),
    columnHelper.accessor("status", {
      id: "status",
      header: "Status",
      enableGrouping: true,
      getGroupingValue: (row) => row.status,
      maxSize: 50,
      size: 50,
      cell: (context) => (
        <span className="flex items-center gap-1 capitalize">
          <Icon
            icon={getStatusIcon(context.getValue())}
            size="sm"
            color={getStatusColor(context.getValue())}
            className="!p-0"
          />
          {context.getValue()}
        </span>
      ),
    }),
    columnHelper.accessor("lastReceived", {
      id: "lastReceived",
      header: "Last Received",
      filterFn: isDateWithinRange,
      minSize: 80,
      maxSize: 80,
      cell: (context) => {
        const value = context.getValue();
        const date = value instanceof Date ? value : new Date(value);
        const isoString = date.toISOString();

        // Get the format from column format settings or use default
        const formatOption = columnTimeFormats[context.column.id] || "timeago";

        return (
          <span title={isoString}>{formatDateTime(date, formatOption)}</span>
        );
      },
    }),
    columnHelper.accessor("assignee", {
      id: "assignee",
      header: "Assignee",
      enableGrouping: true,
      getGroupingValue: (row) => row.assignee,
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
            minSize: 76,
            maxSize: 84,
            cell: (context) => (
              <div className="flex justify-end">
                <AlertMenu
                  presetName={presetName.toLowerCase()}
                  alert={context.row.original}
                  setRunWorkflowModalAlert={setRunWorkflowModalAlert}
                  setDismissModalAlert={setDismissModalAlert}
                  setChangeStatusAlert={setChangeStatusAlert}
                  setTicketModalAlert={setTicketModalAlert}
                  setNoteModalAlert={setNoteModalAlert}
                />
              </div>
            ),
            meta: {
              tdClassName: "p-1 md:p-2",
              thClassName: "p-1 md:p-2",
            },
          }),
        ]
      : []) as ColumnDef<AlertDto>[]),
  ] as ColumnDef<AlertDto>[];
};
