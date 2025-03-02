import { CSSProperties, ReactNode, RefObject } from "react";
import {
  closestCenter,
  DndContext,
  DragEndEvent,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  horizontalListSortingStrategy,
  SortableContext,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  ColumnDef,
  ColumnOrderState,
  VisibilityState,
  flexRender,
  Header,
  Table,
} from "@tanstack/react-table";
import { TableHead, TableHeaderCell, TableRow } from "@tremor/react";
import { AlertDto } from "@/entities/alerts/model";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { getColumnsIds } from "./alert-table-utils";
import { FaArrowUp, FaArrowDown, FaArrowRight } from "react-icons/fa";
import {
  ChevronDownIcon,
  ArrowsUpDownIcon,
  XMarkIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
} from "@heroicons/react/24/outline";
import { BsSortAlphaDown } from "react-icons/bs";
import { BsSortAlphaDownAlt } from "react-icons/bs";

import clsx from "clsx";
import { getCommonPinningStylesAndClassNames } from "@/shared/ui";
import { DropdownMenu } from "@/shared/ui";
import { DEFAULT_COLS_VISIBILITY } from "./alert-table-utils";
import {
  isDateTimeColumn,
  TimeFormatOption,
  createTimeFormatMenuItems,
} from "./alert-table-time-format";

interface DraggableHeaderCellProps {
  header: Header<AlertDto, unknown>;
  table: Table<AlertDto>;
  presetName: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  columnTimeFormats: Record<string, TimeFormatOption>;
  setColumnTimeFormats: (formats: Record<string, TimeFormatOption>) => void;
}

const DraggableHeaderCell = ({
  header,
  table,
  presetName,
  children,
  className,
  style,
  columnTimeFormats,
  setColumnTimeFormats,
}: DraggableHeaderCellProps) => {
  const { column, getResizeHandler } = header;
  const [columnOrder, setColumnOrder] = useLocalStorage<ColumnOrderState>(
    `column-order-${presetName}`,
    getColumnsIds(table.getAllLeafColumns().map((col) => col.columnDef))
  );

  const [columnVisibility, setColumnVisibility] =
    useLocalStorage<VisibilityState>(
      `column-visibility-${presetName}`,
      DEFAULT_COLS_VISIBILITY
    );

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: column.id,
    disabled: column.getIsPinned() !== false,
  });

  const moveColumn = (direction: "left" | "right") => {
    const currentIndex = columnOrder.indexOf(column.id);
    if (direction === "left" && currentIndex > 0) {
      const newOrder = [...columnOrder];
      [newOrder[currentIndex], newOrder[currentIndex - 1]] = [
        newOrder[currentIndex - 1],
        newOrder[currentIndex],
      ];
      setColumnOrder(newOrder);
    } else if (direction === "right" && currentIndex < columnOrder.length - 1) {
      const newOrder = [...columnOrder];
      [newOrder[currentIndex], newOrder[currentIndex + 1]] = [
        newOrder[currentIndex + 1],
        newOrder[currentIndex],
      ];
      setColumnOrder(newOrder);
    }
  };

  const dragStyle: CSSProperties = {
    width:
      column.id === "checkbox"
        ? "32px !important"
        : column.id === "source"
        ? "40px !important"
        : column.getSize(),
    opacity: isDragging ? 0.5 : 1,
    transform: CSS.Translate.toString(transform),
    transition,
    cursor:
      column.getIsPinned() !== false
        ? "default"
        : isDragging
        ? "grabbing"
        : "grab",
  };

  // Hide menu for checkbox, source, severity and alertMenu columns
  const shouldShowMenu =
    column.id !== "checkbox" &&
    column.id !== "source" &&
    column.id !== "severity" &&
    column.id !== "alertMenu";

  const handleColumnVisibilityChange = (
    columnId: string,
    isVisible: boolean
  ) => {
    const newVisibility = {
      ...columnVisibility,
      [columnId]: isVisible,
    };
    setColumnVisibility(newVisibility);
    // Update the table's state as well
    table.setColumnVisibility(newVisibility);
  };

  const getGroupedColumnName = () => {
    const grouping = table.getState().grouping;
    if (grouping.length > 0) {
      // Find the column that's currently grouped
      const groupedColumn = table
        .getAllColumns()
        .find((col) => col.id === grouping[0]);
      return groupedColumn?.columnDef?.header?.toString() || grouping[0];
    }
    return null;
  };

  const isRightmostColumn = () => {
    const visibleColumns = table.getVisibleLeafColumns();

    // name is a special column since it has menu but can't be moved
    if (column.id === "name") {
      // return true so the "move right" option is disabled
      return true;
    }

    // the alertMenu is always the rightmost column
    // so we need to check the second rightmost column
    return column.id === visibleColumns[visibleColumns.length - 2].id;
  };

  const isLeftmostUnpinnedColumn = () => {
    const visibleColumns = table.getVisibleLeafColumns();

    // name is a special column since it has menu but can't be moved
    if (column.id === "name") {
      // return true so the "move left" option is disabled
      return true;
    }

    const firstUnpinnedIndex = visibleColumns.findIndex(
      (col) => !col.getIsPinned()
    );
    return column.id === visibleColumns[firstUnpinnedIndex]?.id;
  };

  return (
    <TableHeaderCell
      className={clsx(
        "relative group",
        column.columnDef.meta?.thClassName,
        (column.getIsPinned() === false || column.id == "name") &&
          "hover:bg-orange-200",
        className
      )}
      style={{ ...dragStyle, ...style }}
      ref={setNodeRef}
    >
      <div
        className={`flex items-center ${
          column.id === "checkbox" ? "justify-center" : "justify-between"
        }`}
        onClick={column.getToggleSortingHandler()}
      >
        <div className="flex items-center" {...listeners} {...attributes}>
          {children}

          {column.getCanSort() && (
            <>
              <div className="w-px h-5 mx-2 bg-gray-400"></div>
              <span
                className="cursor-pointer"
                onClick={(event) => {
                  event.stopPropagation();
                  const toggleSorting = column.getToggleSortingHandler();
                  if (toggleSorting) toggleSorting(event);
                }}
                title={
                  column.getNextSortingOrder() === "asc"
                    ? "Sort ascending"
                    : column.getNextSortingOrder() === "desc"
                      ? "Sort descending"
                      : "Clear sort"
                }
              >
                {column.getIsSorted() ? (
                  column.getIsSorted() === "asc" ? (
                    <FaArrowDown />
                  ) : (
                    <FaArrowUp />
                  )
                ) : (
                  <FaArrowRight />
                )}
              </span>
            </>
          )}
        </div>

        {shouldShowMenu && (
          <DropdownMenu.Menu
            icon={ChevronDownIcon}
            label=""
            className="ml-2 opacity-0 group-hover:opacity-100 transition-opacity"
            iconClassName="group-hover:text-orange-500 transition-colors"
          >
            {column.getCanSort() && (
              <>
                <DropdownMenu.Item
                  icon={BsSortAlphaDown}
                  label="Sort ascending"
                  onClick={() => column.toggleSorting(false)}
                />
                <DropdownMenu.Item
                  icon={BsSortAlphaDownAlt}
                  label="Sort descending"
                  onClick={() => column.toggleSorting(true)}
                />
                {isDateTimeColumn(column.id) &&
                  createTimeFormatMenuItems(
                    column.id,
                    columnTimeFormats,
                    setColumnTimeFormats,
                    DropdownMenu
                  )}
                {column.getCanGroup() !== false && (
                  <DropdownMenu.Item
                    icon={ArrowsUpDownIcon}
                    label={column.getIsGrouped() ? "Ungroup" : "Group by"}
                    disabled={
                      !column.getIsGrouped() &&
                      table.getState().grouping.length > 0
                    }
                    title={
                      !column.getIsGrouped() &&
                      table.getState().grouping.length > 0
                        ? `Only one column can be grouped by at any single time. You should ungroup "${getGroupedColumnName()}"`
                        : undefined
                    }
                    onClick={() => {
                      console.log("Can group:", column.getCanGroup());
                      console.log("Is grouped:", column.getIsGrouped());
                      console.log(
                        "Current grouping state:",
                        table.getState().grouping
                      );
                      console.log("Column ID:", column.id);
                      column.toggleGrouping();
                      console.log(
                        "New grouping state:",
                        table.getState().grouping
                      );
                    }}
                  />
                )}
              </>
            )}
            {column.getCanPin() && (
              <>
                <DropdownMenu.Item
                  icon={ArrowLeftIcon}
                  label="Move column left"
                  onClick={() => moveColumn("left")}
                  disabled={isLeftmostUnpinnedColumn()}
                  title={
                    isLeftmostUnpinnedColumn()
                      ? "This is the leftmost unpinned column"
                      : undefined
                  }
                />
                <DropdownMenu.Item
                  icon={ArrowRightIcon}
                  label="Move column right"
                  onClick={() => moveColumn("right")}
                  disabled={isRightmostColumn()}
                  title={
                    isRightmostColumn()
                      ? "This is the rightmost column"
                      : undefined
                  }
                />
              </>
            )}
            <DropdownMenu.Item
              icon={XMarkIcon}
              label="Remove column"
              onClick={() =>
                handleColumnVisibilityChange(header.column.id, false)
              }
              variant="destructive"
            />
          </DropdownMenu.Menu>
        )}
      </div>

      {column.getIsPinned() === false && (
        <div
          className={clsx(
            "h-full absolute top-0 right-0 w-0.5 cursor-col-resize inline-block opacity-0 group-hover:opacity-100",
            {
              "hover:w-2 bg-blue-100": column.getIsResizing() === false,
              "w-2 bg-blue-400": column.getIsResizing(),
            }
          )}
          onMouseDown={getResizeHandler()}
        />
      )}
    </TableHeaderCell>
  );
};

interface Props {
  columns: ColumnDef<AlertDto>[];
  table: Table<AlertDto>;
  presetName: string;
  a11yContainerRef: RefObject<HTMLDivElement>;
  columnTimeFormats: Record<string, TimeFormatOption>;
  setColumnTimeFormats: (formats: Record<string, TimeFormatOption>) => void;
}

export default function AlertsTableHeaders({
  columns,
  table,
  presetName,
  a11yContainerRef,
  columnTimeFormats,
  setColumnTimeFormats,
}: Props) {
  const [columnOrder, setColumnOrder] = useLocalStorage<ColumnOrderState>(
    `column-order-${presetName}`,
    getColumnsIds(columns)
  );

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        delay: 250,
        tolerance: 5,
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: 250,
        tolerance: 5,
      },
    })
  );

  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over?.id == null) return;

    const fromIndex = columnOrder.indexOf(active.id as string);
    const toIndex = columnOrder.indexOf(over.id as string);

    if (toIndex === -1) {
      return;
    }

    const reorderedCols = [...columnOrder];
    const reorderedItem = reorderedCols.splice(fromIndex, 1);
    reorderedCols.splice(toIndex, 0, reorderedItem[0]);

    setColumnOrder(reorderedCols);
  };

  return (
    <TableHead>
      {table.getHeaderGroups().map((headerGroup) => (
        <DndContext
          key={headerGroup.id}
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={onDragEnd}
          accessibility={{
            container: a11yContainerRef.current ?? undefined,
          }}
        >
          <TableRow key={headerGroup.id}>
            <SortableContext
              items={headerGroup.headers}
              strategy={horizontalListSortingStrategy}
            >
              {headerGroup.headers.map((header) => {
                const { style, className } =
                  getCommonPinningStylesAndClassNames(
                    header.column,
                    table.getState().columnPinning.left?.length,
                    table.getState().columnPinning.right?.length
                  );
                return (
                  <DraggableHeaderCell
                    key={header.column.columnDef.id}
                    header={header}
                    table={table}
                    presetName={presetName}
                    className={className}
                    style={style}
                    columnTimeFormats={columnTimeFormats}
                    setColumnTimeFormats={setColumnTimeFormats}
                  >
                    {header.isPlaceholder ? null : (
                      <div>
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                      </div>
                    )}
                  </DraggableHeaderCell>
                );
              })}
            </SortableContext>
          </TableRow>
        </DndContext>
      ))}
    </TableHead>
  );
}
