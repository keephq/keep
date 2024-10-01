import React, { useEffect, useState } from "react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import {
  Callout,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Button,
  Badge,
} from "@tremor/react";
import { ExclamationTriangleIcon } from "@radix-ui/react-icons";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { IncidentDto } from "../models";
import IncidentPagination from "../incident-pagination";
import {
  PaginatedWorkflowExecutionDto,
  WorkflowExecution,
} from "app/workflows/builder/types";
import { useIncidentWorkflowExecutions } from "utils/hooks/useIncidents";
import { useRouter } from "next/navigation";
import {
  getIcon,
  getTriggerIcon,
  extractTriggerValue,
  extractTriggerDetails,
} from "app/workflows/[workflow_id]/workflow-execution-table";
import IncidentWorkflowSidebar from "./incident-workflow-sidebar";

interface Props {
  incident: IncidentDto;
}

interface Pagination {
  limit: number;
  offset: number;
}

const columnHelper = createColumnHelper<WorkflowExecution>();

export default function IncidentWorkflowTable({ incident }: Props) {
  const router = useRouter();
  const [workflowsPagination, setWorkflowsPagination] = useState<Pagination>({
    limit: 20,
    offset: 0,
  });
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedExecution, setSelectedExecution] =
    useState<WorkflowExecution | null>(null);

  const { data: workflows, isLoading } = useIncidentWorkflowExecutions(
    incident.id,
    workflowsPagination.limit,
    workflowsPagination.offset
  );

  const [pagination, setTablePagination] = useState({
    pageIndex: workflows ? Math.ceil(workflows.offset / workflows.limit) : 0,
    pageSize: workflows ? workflows.limit : 20,
  });

  useEffect(() => {
    if (workflows && workflows.limit != pagination.pageSize) {
      setWorkflowsPagination({
        limit: pagination.pageSize,
        offset: 0,
      });
    }
    const currentOffset = pagination.pageSize * pagination.pageIndex;
    if (workflows && workflows.offset != currentOffset) {
      setWorkflowsPagination({
        limit: pagination.pageSize,
        offset: currentOffset,
      });
    }
  }, [pagination, workflows]);

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  const handleRowClick = (execution: WorkflowExecution) => {
    setSelectedExecution(execution);
    toggleSidebar();
  };

  const columns = [
    columnHelper.accessor("workflow_name", {
      header: "Name",
      cell: (info) => info.getValue() || "Unnamed Workflow",
    }),
    columnHelper.accessor("status", {
      header: "Status",
      cell: (info) => getIcon(info.getValue()),
    }),
    columnHelper.accessor("started", {
      header: "Start Time",
      cell: (info) => new Date(info.getValue()).toLocaleString(),
    }),
    columnHelper.display({
      id: "execution_time",
      header: "Duration",
      cell: ({ row }) => {
        const customFormatter = (seconds: number | null) => {
          if (seconds === undefined || seconds === null) {
            return "";
          }

          const hours = Math.floor(seconds / 3600);
          const minutes = Math.floor((seconds % 3600) / 60);
          const remainingSeconds = seconds % 60;

          if (hours > 0) {
            return `${hours} hr ${minutes}m ${remainingSeconds}s`;
          } else if (minutes > 0) {
            return `${minutes}m ${remainingSeconds}s`;
          } else {
            return `${remainingSeconds.toFixed(2)}s`;
          }
        };

        return (
          <div>{customFormatter(row.original.execution_time ?? null)}</div>
        );
      },
    }),
    columnHelper.display({
      id: "triggered_by",
      header: "Trigger",
      cell: ({ row }) => {
        const triggered_by = row.original.triggered_by;
        const valueToShow = extractTriggerValue(triggered_by);

        return triggered_by ? (
          <div className="flex items-center gap-2">
            <Button
              className="px-3 py-1 bg-orange-100 text-black rounded-xl border-2 border-orange-400 inline-flex items-center gap-2 font-bold hover:bg-orange-200"
              variant="secondary"
              tooltip={triggered_by ?? ""}
              icon={getTriggerIcon(valueToShow)}
            >
              <div>{valueToShow}</div>
            </Button>
          </div>
        ) : null;
      },
    }),
    columnHelper.display({
      id: "triggered_by_details",
      header: "Trigger Details",
      cell: ({ row }) => {
        const triggered_by = row.original.triggered_by;
        const details = extractTriggerDetails(triggered_by);
        return triggered_by ? (
          <div className="flex items-center gap-2 flex-wrap">
            {details.map((detail, index) => (
              <Badge key={index} className="px-3 py-1" color="orange">
                {detail}
              </Badge>
            ))}
          </div>
        ) : null;
      },
    }),
  ];

  const table = useReactTable({
    columns,
    data: workflows?.items ?? [],
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: workflows ? Math.ceil(workflows.count / workflows.limit) : -1,
    state: {
      pagination,
    },
    onPaginationChange: setTablePagination,
  });

  return (
    <>
      {!isLoading && (workflows?.items ?? []).length === 0 && (
        <Callout
          className="mt-4 w-full"
          title="No Workflows"
          icon={ExclamationTriangleIcon}
          color="orange"
        >
          No workflows have been executed for this incident yet.
        </Callout>
      )}

      <Table>
        <TableHead>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHeaderCell key={header.id}>
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext()
                  )}
                </TableHeaderCell>
              ))}
            </TableRow>
          ))}
        </TableHead>
        {workflows && workflows.items.length > 0 && (
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                className="hover:bg-slate-100 cursor-pointer"
                onClick={() => handleRowClick(row.original)}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        )}
        {(isLoading || (workflows?.items ?? []).length === 0) && (
          <TableBody>
            {Array(pagination.pageSize)
              .fill("")
              .map((_, index) => (
                <TableRow key={`skeleton-${index}`}>
                  {columns.map((_, cellIndex) => (
                    <TableCell key={`cell-${cellIndex}`}>
                      <Skeleton />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
          </TableBody>
        )}
      </Table>

      <div className="mt-4 mb-8">
        <IncidentPagination table={table} isRefreshAllowed={true} />
      </div>

      {selectedExecution ? (
        <IncidentWorkflowSidebar
          isOpen={isSidebarOpen}
          toggle={toggleSidebar}
          selectedExecution={selectedExecution}
        />
      ) : null}
    </>
  );
}
