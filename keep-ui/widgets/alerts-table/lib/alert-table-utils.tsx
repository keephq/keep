import { useState } from "react";
import {
  ColumnDef,
  FilterFn,
  RowSelectionState,
  VisibilityState,
  createColumnHelper,
  Cell,
  AccessorKeyColumnDef,
} from "@tanstack/react-table";
import { AlertDto } from "@/entities/alerts/model";
import { Accordion, AccordionBody, AccordionHeader, Icon } from "@tremor/react";
import { AlertName } from "@/entities/alerts/ui";
import AlertAssignee from "../ui/alert-assignee";
import AlertExtraPayload from "../ui/alert-extra-payload";
import { AlertMenu } from "@/features/alerts/alert-menu";
import { isSameDay, isValid, isWithinInterval } from "date-fns";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import {
  isListColumn,
  formatList,
  ListFormatOption,
  ListItem,
} from "@/widgets/alerts-table/lib/alert-table-list-format";
import {
  MdOutlineNotificationsActive,
  MdOutlineNotificationsOff,
} from "react-icons/md";
import { getStatusIcon, getStatusColor } from "@/shared/lib/status-utils";
import { useConfig } from "@/utils/hooks/useConfig";
import {
  TableIndeterminateCheckbox,
  TableSeverityCell,
  UISeverity,
} from "@/shared/ui";
import { DynamicImageProviderIcon, Link } from "@/components/ui";
import clsx from "clsx";
import {
  RowStyle,
  useAlertRowStyle,
} from "@/entities/alerts/model/useAlertRowStyle";
import {
  formatDateTime,
  TimeFormatOption,
  isDateTimeColumn,
} from "@/widgets/alerts-table/lib/alert-table-time-format";
import { useIncidents } from "@/utils/hooks/useIncidents";
import { useExpandedRows } from "@/utils/hooks/useExpandedRows";
import {
  ColumnRenameMapping,
  getColumnDisplayName,
} from "@/widgets/alerts-table/ui/alert-table-column-rename";

export const DEFAULT_COLS = [
  "severity",
  "checkbox",
  "noise",
  "source",
  "status",
  "name",
  "description",
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
  row: {
    id: string;
    original?: AlertDto;
  },
  theme: Record<string, string>,
  lastViewedAlert: string | null,
  rowStyle: RowStyle,
  expanded?: boolean
) => {
  const severity = row.original?.severity || "info";
  const rowBgColor = theme[severity] || "bg-white";
  const isLastViewed = row.original?.fingerprint === lastViewedAlert;

  return clsx(
    "cursor-pointer group",
    isLastViewed ? "bg-orange-50" : rowBgColor,
    // Expanded rows should have auto height with a larger minimum height
    expanded ? "h-auto min-h-16" : rowStyle === "default" ? "h-8" : "h-12",
    // More padding for expanded rows
    expanded
      ? "[&>td]:p-3"
      : rowStyle === "default"
        ? "[&>td]:px-0.5 [&>td]:py-0"
        : "[&>td]:p-2",
    "hover:bg-orange-100"
  );
};

type CustomCell = {
  column: {
    id: string;
    columnDef: {
      meta: {
        tdClassName: string;
      };
    };
  };
};

export const getCellClassName = (
  cell: Cell<any, unknown> | CustomCell,
  className: string,
  rowStyle: RowStyle,
  isLastViewed: boolean,
  expanded?: boolean
) => {
  const isNameCell = cell.column.id === "name";
  const isDescriptionCell = cell.column.id === "description";
  const tdClassName =
    "getValue" in cell
      ? cell.column.columnDef.meta?.tdClassName || ""
      : cell.column.columnDef.meta.tdClassName;

  return clsx(
    tdClassName,
    className,
    isNameCell && "name-cell",
    // For dense rows, make sure name cells don't expand too much, unless expanded
    rowStyle === "default" && isNameCell && !expanded && "w-auto max-w-2xl",
    // Remove truncation for expanded rows
    isDescriptionCell && expanded && "whitespace-pre-wrap break-words",
    // Remove line clamp for expanded rows
    expanded && "!whitespace-pre-wrap !overflow-visible",
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
  MenuComponent?: (alert: AlertDto) => React.ReactNode;
  extraColumns?: AccessorKeyColumnDef<AlertDto, boolean | undefined>[];
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
    MenuComponent,
    extraColumns = [],
  }: GenerateAlertTableColsArg = { presetName: "feed" }
) => {
  const [expandedToggles, setExpandedToggles] = useState<RowSelectionState>({});
  const [rowStyle] = useAlertRowStyle();
  const [columnTimeFormats] = useLocalStorage<Record<string, TimeFormatOption>>(
    `column-time-formats-${presetName}`,
    {}
  );
  const { data: incidents } = useIncidents();
  const { isRowExpanded } = useExpandedRows(presetName);
  const [columnListFormats, setColumnListFormats] = useLocalStorage<
    Record<string, ListFormatOption>
  >(`column-list-formats-${presetName}`, {});
  const { data: configData } = useConfig();
  // check if noisy alerts are enabled
  const noisyAlertsEnabled = configData?.NOISY_ALERTS_ENABLED;
  const [columnRenameMapping] = useLocalStorage<ColumnRenameMapping>(
    `column-rename-mapping-${presetName}`,
    {}
  );

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
        header: getColumnDisplayName(colName, colName, columnRenameMapping),
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
          const row = context.row;
          const isExpanded = isRowExpanded?.(row.original.fingerprint);

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

          if (context.column.id === "incident") {
            const incidentString = String(value || "");
            const incidentSplit = incidentString.split(",");
            return (
              <div className="flex flex-wrap gap-1 w-full overflow-hidden">
                {incidentSplit.map((incidentId, index) => {
                  const incident = incidents?.items.find(
                    (incident) => incident.id === incidentId
                  );
                  if (!incident) return null;
                  const title =
                    incident.user_generated_name || incident.ai_generated_name;
                  return (
                    <Link
                      key={incidentId}
                      href={`/incidents/${incidentId}`}
                      title={title}
                    >
                      {title}
                    </Link>
                  );
                })}
              </div>
            );
          }

          let isList = isListColumn(context.column);
          let listFormatOption =
            columnListFormats[context.column.id] || "badges";
          if (isList) {
            // Type check and convert value to the expected type for formatList
            if (typeof value === "string") {
              return formatList(value, listFormatOption);
            } else if (
              Array.isArray(value) &&
              value.every(
                (item) =>
                  typeof item === "object" && item !== null && "label" in item
              )
            ) {
              return formatList(value as ListItem[], listFormatOption);
            } else {
              // Fallback for incompatible types
              return String(value || "");
            }
          }

          if (value) {
            return (
              <div
                className={clsx(
                  "whitespace-pre-wrap",
                  // Only apply line clamp if not expanded
                  !isExpanded &&
                    (rowStyle === "default" ? "line-clamp-1" : "line-clamp-3")
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
    columnHelper.accessor("status", {
      id: "status",
      header: () => <></>, // Empty header like source column
      enableGrouping: true,
      getGroupingValue: (row) => row.status,
      maxSize: 16,
      minSize: 16,
      size: 16,
      enableResizing: false,
      cell: (context) => (
        <div className="flex items-center justify-center">
          <Icon
            icon={getStatusIcon(context.getValue())}
            size="sm"
            color={getStatusColor(context.getValue())}
            className="!p-0 h-32px w-32px"
            tooltip={context.getValue()}
          />
        </div>
      ),
      meta: {
        tdClassName: "!p-0 w-4 sm:w-8 !box-border", // Same styling as source
        thClassName: "!p-0 w-4 sm:w-8 !box-border",
      },
    }),
    // Source column with exact 40px width ( see alert-table-headers )
    columnHelper.accessor("source", {
      id: "source",
      header: () => <></>,
      minSize: 24,
      maxSize: 24,
      size: 24, // Fixed size that won't change
      enableSorting: false,
      getGroupingValue: (row) => row.source,
      enableResizing: false,
      cell: (context) => {
        return (
          <div className="flex items-center justify-center w-[24px] h-[24px]">
            {context.getValue().map((source, index) => {
              return (
                <DynamicImageProviderIcon
                  className={clsx(
                    "inline-block",
                    // Use fixed pixel sizes instead of responsive sizing
                    "size-6",
                    index == 0 ? "" : "-ml-2"
                  )}
                  key={source}
                  alt={source}
                  height={24}
                  width={24}
                  title={source}
                  providerType={source}
                  src={`/icons/${source}-icon.png`}
                  id={`${source}-icon-${index}`}
                />
              );
            })}
          </div>
        );
      },
      meta: {
        tdClassName: "!p-1 w-10 !box-border !flex-none", // Force fixed width with flex-none
        thClassName: "!p-1 w-10 !box-border !flex-none",
      },
    }),
    // Name column butted up against source
    columnHelper.accessor("name", {
      id: "name",
      header: getColumnDisplayName("name", "Name", columnRenameMapping),
      enableGrouping: true,
      enableResizing: true,
      getGroupingValue: (row) => row.name,
      // Set fixed maximum size to prevent overflow
      minSize: 150,
      maxSize: 200, // Reduce from 250 to 200 to constrain more tightly
      // Use a consistent width for all row states
      size: 180, // Add a fixed size to ensure consistent width
      cell: (context) => {
        const row = context.row;
        const expanded = isRowExpanded?.(row.original.fingerprint);

        return (
          // Remove w-full class which can cause expansion
          <div className={expanded ? "max-w-[180px] overflow-hidden" : ""}>
            <AlertName
              alert={context.row.original}
              expanded={expanded}
              // Remove flex-grow which can cause expansion
              className={expanded ? "max-w-[180px] overflow-hidden" : ""}
            />
          </div>
        );
      },
      meta: {
        // Remove w-full from tdClassName to prevent automatic expansion
        tdClassName: "name-cell",
        thClassName: "name-cell",
      },
    }),

    columnHelper.accessor("description", {
      id: "description",
      header: getColumnDisplayName(
        "description",
        "Description",
        columnRenameMapping
      ),
      enableGrouping: true,
      // Increase default minSize to give description more space
      minSize: 200,
      // Let it grow more when expanded
      cell: (context) => {
        const value = context.getValue();
        const row = context.row;
        const expanded = isRowExpanded?.(row.original.fingerprint);

        return (
          <div
            title={expanded ? undefined : value}
            className={clsx(
              // Give description more space and control overflow
              expanded ? "w-full break-words" : "",
              // Set fixed width when expanded to prevent layout issues
              expanded ? "max-w-[100%]" : ""
            )}
          >
            <div
              className={clsx(
                // Always use whitespace-pre-wrap for consistency
                "whitespace-pre-wrap",
                // Only truncate when not expanded
                !expanded &&
                  (rowStyle === "default"
                    ? "truncate line-clamp-1"
                    : "truncate line-clamp-3")
              )}
            >
              {value}
            </div>
          </div>
        );
      },
    }),
    columnHelper.accessor("lastReceived", {
      id: "lastReceived",
      header: getColumnDisplayName(
        "lastReceived",
        "Last Received",
        columnRenameMapping
      ),
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
      header: getColumnDisplayName("assignee", "Assignee", columnRenameMapping),
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
    ...extraColumns,
    ...((isMenuDisplayed
      ? [
          columnHelper.display({
            id: "alertMenu",
            minSize: 120,
            cell: (context) =>
              MenuComponent ? (
                MenuComponent(context.row.original)
              ) : (
                <AlertMenu
                  presetName={presetName.toLowerCase()}
                  alert={context.row.original}
                  setRunWorkflowModalAlert={setRunWorkflowModalAlert}
                  setDismissModalAlert={setDismissModalAlert}
                  setChangeStatusAlert={setChangeStatusAlert}
                  setTicketModalAlert={setTicketModalAlert}
                  setNoteModalAlert={setNoteModalAlert}
                />
              ),
            meta: {
              tdClassName: "p-0 md:p-2",
              thClassName: "p-0 md:p-2",
            },
          }),
        ]
      : []) as ColumnDef<AlertDto>[]),
  ] as ColumnDef<AlertDto>[];
};
