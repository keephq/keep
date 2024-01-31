// culled from https://github.com/cpvalente/ontime/blob/master/apps/client/src/features/cuesheet/cuesheet-table-elements/CuesheetHeader.tsx

import { ReactNode } from "react";
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
  Column,
  ColumnDef,
  ColumnOrderState,
  flexRender,
  Table,
} from "@tanstack/react-table";
import { TableHead, TableHeaderCell, TableRow } from "@tremor/react";
import { AlertDto } from "./models";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { getColumnsIds } from "./alert-table-utils";

interface DraggableHeaderCellProps {
  column: Column<AlertDto, unknown>;
  children: ReactNode;
}

const DraggableHeaderCell = ({
  column,
  children,
}: DraggableHeaderCellProps) => {
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

  const dragStyle = {
    opacity: isDragging ? 0.5 : 1,
    transform: CSS.Translate.toString(transform),
    transition,
  };

  return (
    <TableHeaderCell
      style={dragStyle}
      className={column.getIsPinned() ? "" : `hover:bg-slate-100 cursor-grab`}
      ref={setNodeRef}
    >
      <span className="flex cursor-grab" {...attributes} {...listeners}>
        {children}
      </span>
    </TableHeaderCell>
  );
};

interface Props {
  columns: ColumnDef<AlertDto>[];
  table: Table<AlertDto>;
  presetName: string;
}

export default function AlertsTableHeaders({
  columns,
  table,
  presetName,
}: Props) {
  const [columnOrder, setColumnOrder] = useLocalStorage<ColumnOrderState>(
    `column-order-${presetName}`,
    getColumnsIds(columns)
  );

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        delay: 100,
        tolerance: 50,
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: 100,
        tolerance: 50,
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
                    column={header.column}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
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
