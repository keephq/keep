// culled from https://github.com/cpvalente/ontime/blob/master/apps/client/src/features/cuesheet/cuesheet-table-elements/CuesheetHeader.tsx

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
import { AlertDto } from "./models";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { getColumnsIds } from "./alert-table-utils";
import { FaArrowUp, FaArrowDown, FaArrowRight } from "react-icons/fa";
import clsx from "clsx";
import { getCommonPinningStylesAndClassNames } from "@/components/ui/table/utils";

interface DraggableHeaderCellProps {
  header: Header<AlertDto, unknown>;
  children: ReactNode;
}

const DraggableHeaderCell = ({
  header,
  children,
}: DraggableHeaderCellProps) => {
  const { column, getResizeHandler } = header;

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

  const dragStyle: CSSProperties = {
    width: column.getSize(),
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

  // TODO: fix multiple pinned columns
  // const { style, className } = getCommonPinningStylesAndClassNames(column);

  return (
    <TableHeaderCell
      className={clsx(
        "relative",
        column.columnDef.meta?.thClassName,
        column.getIsPinned() === false && "hover:bg-slate-100"
      )}
      style={dragStyle}
      ref={setNodeRef}
    >
      <div className="flex items-center" {...listeners}>
        {/* Flex container */}
        {column.getCanSort() && ( // Sorting icon to the left
          <>
            <span
              className="cursor-pointer" // Ensures clickability of the icon
              onClick={(event) => {
                console.log("clicked for sorting");
                event.stopPropagation();
                const toggleSorting = header.column.getToggleSortingHandler();
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
              {/* Icon logic */}
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
            {/* Custom styled vertical line separator */}
            <div className="w-px h-5 mx-2 bg-gray-400"></div>
          </>
        )}
        {children} {/* Column name or text */}
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
        delay: 250, // Adjust delay to prevent drag on quick clicks
        tolerance: 5, // Adjust tolerance based on needs
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
              key={headerGroup.id}
              items={headerGroup.headers}
              strategy={horizontalListSortingStrategy}
            >
              {headerGroup.headers.map((header) => {
                return (
                  <DraggableHeaderCell
                    key={header.column.columnDef.id}
                    header={header}
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
