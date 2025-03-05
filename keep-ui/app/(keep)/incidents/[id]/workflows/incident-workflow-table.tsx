"use client";

import type { IncidentDto } from "@/entities/incidents/model";
import { ExclamationTriangleIcon } from "@radix-ui/react-icons";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import {
  Badge,
  Button,
  Callout,
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import {
  extractTriggerDetails,
  extractTriggerValue,
  getIcon,
  getTriggerIcon,
} from "@/app/(keep)/workflows/[workflow_id]/workflow-execution-table";
import { WorkflowExecutionDetail } from "@/shared/api/workflow-executions";
import { useEffect, useState } from "react";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { useIncidentWorkflowExecutions } from "utils/hooks/useIncidents";
import { IncidentWorkflowsEmptyState } from "./incident-workflow-empty";
import IncidentWorkflowSidebar from "./incident-workflow-sidebar";
import { TablePagination } from "@/shared/ui";

interface Props {
  incident: IncidentDto;
}

interface Pagination {
  limit: number;
  offset: number;
}

const columnHelper = createColumnHelper<WorkflowExecutionDetail>();

export default function IncidentWorkflowTable({ incident }: Props) {
  const [workflowsPagination, setWorkflowsPagination] = useState<Pagination>({
    limit: 20,
    offset: 0,
  });
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedExecution, setSelectedExecution] =
    useState<WorkflowExecutionDetail | null>(null);

  const {
    data: workflows,
    isLoading: _workflowsLoading,
    error: workflowsError,
  } = useIncidentWorkflowExecutions(
    incident.id,
    workflowsPagination.limit,
    workflowsPagination.offset
  );

  // TODO: Load data on server side
  // Loading state is true if the data is not loaded and there is no error for smoother loading state on initial load
  const isLoading = _workflowsLoading || (!workflows && !workflowsError);

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

  const handleRowClick = (execution: WorkflowExecutionDetail) => {
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
    getRowId: (row) => row.id,
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

  if (!isLoading && (workflows?.items ?? []).length === 0) {
    return <IncidentWorkflowsEmptyState incident={incident} />;
  }

  return (
    <>
      <Card className="p-0 overflow-hidden">
        {!isLoading && (workflows?.items ?? []).length === 0 && (
          <Callout
            className="m-4"
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
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          )}
          {isLoading && (
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
      </Card>

      <div className="mt-4 mb-8">
        <TablePagination table={table} />
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
