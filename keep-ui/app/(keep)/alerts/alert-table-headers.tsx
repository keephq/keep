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
  EyeIcon,
  ArrowsUpDownIcon,
  ChevronDoubleRightIcon,
  ChevronDoubleLeftIcon,
  XMarkIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
} from "@heroicons/react/24/outline";
import { BsSortAlphaDown } from "react-icons/bs";
import { BsSortAlphaDownAlt } from "react-icons/bs";

import clsx from "clsx";
import { getCommonPinningStylesAndClassNames } from "@/shared/ui";
import { DropdownMenu } from "@/shared/ui";

interface DraggableHeaderCellProps {
  header: Header<AlertDto, unknown>;
  table: Table<AlertDto>;
  presetName: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

const DraggableHeaderCell = ({
  header,
  table,
  presetName,
  children,
  className,
  style,
}: DraggableHeaderCellProps) => {
  const { column, getResizeHandler } = header;
  const [columnOrder, setColumnOrder] = useLocalStorage<ColumnOrderState>(
    `column-order-${presetName}`,
    getColumnsIds(table.getAllLeafColumns().map((col) => col.columnDef))
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

  return (
    <TableHeaderCell
      className={clsx(
        "relative group",
        column.columnDef.meta?.thClassName,
        column.getIsPinned() === false && "hover:bg-orange-200",
        className
      )}
      style={{ ...dragStyle, ...style }}
      ref={setNodeRef}
    >
      <div
        className={`flex items-center justify-between ${
          column.id === "checkbox" ? "justify-center" : ""
        }`}
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
              {column.getCanGroup() !== false && (
                <DropdownMenu.Item
                  icon={ArrowsUpDownIcon}
                  label={column.getIsGrouped() ? "Ungroup" : "Group by"}
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
                icon={ChevronDoubleLeftIcon}
                label={column.getIsPinned() ? "Unpin column" : "Pin column"}
                onClick={() =>
                  column.pin(column.getIsPinned() ? false : "left")
                }
              />
              <DropdownMenu.Item
                icon={ArrowLeftIcon}
                label="Move column left"
                onClick={() => moveColumn("left")}
              />
              <DropdownMenu.Item
                icon={ArrowRightIcon}
                label="Move column right"
                onClick={() => moveColumn("right")}
              />
            </>
          )}
          <DropdownMenu.Item
            icon={EyeIcon}
            label="Hide column"
            onClick={() => column.toggleVisibility(false)}
          />
          <DropdownMenu.Item
            icon={XMarkIcon}
            label="Remove column"
            onClick={() => column.toggleVisibility(false)}
            variant="destructive"
          />
        </DropdownMenu.Menu>
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
}

export default function AlertsTableHeaders({
  columns,
  table,
  presetName,
  a11yContainerRef,
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
