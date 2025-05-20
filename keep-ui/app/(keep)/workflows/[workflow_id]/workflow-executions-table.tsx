import { Dispatch, SetStateAction } from "react";
import {
  createColumnHelper,
  DisplayColumnDef,
  Row,
} from "@tanstack/react-table";
import {
  PaginatedWorkflowExecutionDto,
  WorkflowExecutionDetail,
} from "@/shared/api/workflow-executions";
import { GenericTable } from "@/components/table/GenericTable";
import { EllipsisHorizontalIcon } from "@heroicons/react/20/solid";
import TimeAgo, { Formatter, Suffix, Unit } from "react-timeago";
import { formatDistanceToNowStrict } from "date-fns";
import { Badge } from "@tremor/react";
import { useRouter } from "next/navigation";
import {
  ArrowUpRightIcon,
  ClipboardDocumentIcon,
} from "@heroicons/react/24/outline";
import {
  DropdownMenu,
  getIconForStatusString,
  showErrorToast,
  showSuccessToast,
} from "@/shared/ui";
import { Link } from "@/components/ui";
import {
  extractTriggerDetailsV2,
  getTriggerIcon,
} from "@/entities/workflows/lib/ui-utils";
import { TableFilters } from "./table-filters";

interface Pagination {
  limit: number;
  offset: number;
}

interface WorkflowExecutionsTableProps {
  workflowName: string;
  workflowId: string;
  executions: PaginatedWorkflowExecutionDto;
  setPagination: Dispatch<SetStateAction<Pagination>>;
  currentRevision: number;
}

function WorkflowExecutionRowMenu({
  row,
}: {
  row: Row<WorkflowExecutionDetail>;
}) {
  const router = useRouter();
  return (
    <DropdownMenu.Menu
      icon={EllipsisHorizontalIcon}
      label=""
      onClick={(e) => e.stopPropagation()}
    >
      <DropdownMenu.Item
        icon={ArrowUpRightIcon}
        label="View Logs"
        onClick={() => {
          router.push(
            `/workflows/${row.original.workflow_id}/runs/${row.original.id}`
          );
        }}
      />
      <DropdownMenu.Item
        icon={ClipboardDocumentIcon}
        label="Copy Execution ID"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(row.original.id);
            showSuccessToast("Execution ID copied to clipboard");
          } catch (err) {
            showErrorToast(
              err,
              "Failed to copy execution id. Please check your browser permissions."
            );
          }
        }}
      />
    </DropdownMenu.Menu>
  );
}

export function WorkflowExecutionsTable({
  workflowName,
  workflowId,
  executions,
  setPagination,
  currentRevision,
}: WorkflowExecutionsTableProps) {
  const columnHelper = createColumnHelper<WorkflowExecutionDetail>();

  const columns = [
    columnHelper.display({
      id: "status",
      header: "Status",
      cell: ({ row }) => {
        const status = row.original.status;
        return <div>{getIconForStatusString(status)}</div>;
      },
    }),
    columnHelper.display({
      id: "workflow_revision",
      header: "Workflow",
      cell: ({ row }) => {
        return (
          <>
            <Link
              href={`/workflows/${row.original.workflow_id}/runs/${row.original.id}`}
            >
              {workflowName} · Rev. {row.original.workflow_revision}
            </Link>
            {row.original.workflow_revision === currentRevision ? (
              <Badge color="green" size="xs" className="ml-1">
                Current
              </Badge>
            ) : null}
          </>
        );
      },
    }),
    columnHelper.display({
      id: "triggered_by",
      header: "Triggered by",
      cell: ({ row }) => {
        const triggered_by = row.original.triggered_by;
        const { type, details } = extractTriggerDetailsV2(triggered_by);

        let detailsContent: React.ReactNode = type as string;

        if (type === "incident") {
          detailsContent = (
            <Link
              href={`/incidents/${details.id}`}
              target="_blank"
              onClick={(e) => e.stopPropagation()}
            >
              {details.name}
            </Link>
          );
        }
        if (type === "alert") {
          detailsContent = (
            <Link
              href={`/alerts/feed/?cel=${encodeURIComponent(
                `id=="${details.id}"`
              )}`}
              onClick={(e) => e.stopPropagation()}
            >
              Alert &quot;{details.name}&quot;
            </Link>
          );
        }
        if (type === "manual") {
          detailsContent = `Manually by ${details.user}`;
        }
        if (type === "interval") {
          detailsContent = `Interval`;
        }
        return (
          <>
            <Badge
              color="gray"
              tooltip={Object.entries(details)
                .map(([key, value]) => `${key}: ${value}`)
                .join(", ")}
              icon={getTriggerIcon(type)}
            >
              {detailsContent}
            </Badge>
          </>
        );
      },
    }),
    columnHelper.display({
      id: "execution_time",
      header: "Execution Duration",
      cell: ({ row }) => {
        const customFormatter = (seconds: number | null) => {
          if (seconds === undefined || seconds === null) {
            return "";
          }

          if (seconds === 0) {
            return "0s";
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
      id: "started",
      header: "Started at",
      cell: ({ row }) => {
        const customFormatter: Formatter = (
          value: number,
          unit: Unit,
          suffix: Suffix
        ) => {
          if (!row?.original?.started) {
            return "";
          }

          const formattedString = formatDistanceToNowStrict(
            new Date(row.original.started + "Z"),
            { addSuffix: true }
          );

          return formattedString
            .replace("about ", "")
            .replace("minute", "min")
            .replace("second", "sec")
            .replace("hour", "hr");
        };
        return (
          <TimeAgo
            date={row.original.started + "Z"}
            formatter={customFormatter}
          />
        );
      },
    }),
    columnHelper.display({
      id: "menu",
      header: "",
      cell: ({ row }) => <WorkflowExecutionRowMenu row={row} />,
    }),
  ] as DisplayColumnDef<WorkflowExecutionDetail>[];

  // TODO: add pagination state to the url search params
  return (
    <>
      <TableFilters workflowId={workflowId} />
      <GenericTable<WorkflowExecutionDetail>
        data={executions.items}
        columns={columns}
        rowCount={executions.count ?? 0} // Assuming pagination is not needed, you can adjust this if you have pagination
        offset={executions.offset} // Customize as needed
        limit={executions.limit} // Customize as needed
        onPaginationChange={(newLimit: number, newOffset: number) =>
          setPagination({ limit: newLimit, offset: newOffset })
        }
      />
    </>
  );
}
