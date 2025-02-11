import { createColumnHelper, DisplayColumnDef } from "@tanstack/react-table";
import { GenericTable } from "@/components/table/GenericTable";
import {
  MappingExecutionDetail,
  PaginatedMappingExecutionDto,
} from "@/shared/api/mapping-executions";
import { Dispatch, SetStateAction } from "react";
import { useRouter } from "next/navigation";
import { getIcon } from "../../workflows/[workflow_id]/workflow-execution-table";
import TimeAgo from "react-timeago";
import { formatDistanceToNowStrict } from "date-fns";

interface Pagination {
  limit: number;
  offset: number;
}

interface Props {
  executions: PaginatedMappingExecutionDto;
  setPagination: Dispatch<SetStateAction<Pagination>>;
}

export function MappingExecutionTable({ executions, setPagination }: Props) {
  const columnHelper = createColumnHelper<MappingExecutionDetail>();
  const router = useRouter();

  const columns = [
    columnHelper.display({
      id: "status",
      header: "Status",
      cell: ({ row }) => {
        const status = row.original.status;
        return <div>{getIcon(status)}</div>;
      },
    }),
    columnHelper.display({
      id: "id",
      header: "Execution ID",
      cell: ({ row }) => {
        const status = row.original.status;
        const isError = ["error", "failed", "timeout"].includes(status);
        return (
          <div className={`${isError ? "text-red-500" : ""}`}>
            {row.original.id}
          </div>
        );
      },
    }),
    columnHelper.display({
      id: "alert_id",
      header: "Alert ID",
      cell: ({ row }) => row.original.alert_id,
    }),
    columnHelper.display({
      id: "execution_time",
      header: "Duration",
      cell: ({ row }) => {
        const seconds = row.original.execution_time;
        if (!seconds) return "";
        return seconds > 60
          ? `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
          : `${seconds.toFixed(2)}s`;
      },
    }),
    columnHelper.display({
      id: "started",
      header: "Started",
      cell: ({ row }) => (
        <TimeAgo
          date={row.original.started + "Z"}
          formatter={(value, unit, suffix) => {
            if (!row.original.started) return "";
            return formatDistanceToNowStrict(
              new Date(row.original.started + "Z"),
              {
                addSuffix: true,
              }
            )
              .replace("about ", "")
              .replace("minute", "min")
              .replace("second", "sec")
              .replace("hour", "hr");
          }}
        />
      ),
    }),
  ] as DisplayColumnDef<MappingExecutionDetail>[];

  return (
    <GenericTable<MappingExecutionDetail>
      data={executions.items}
      columns={columns}
      rowCount={executions.count}
      offset={executions.offset}
      limit={executions.limit}
      onPaginationChange={(newLimit: number, newOffset: number) =>
        setPagination({ limit: newLimit, offset: newOffset })
      }
      onRowClick={(row: MappingExecutionDetail) => {
        router.push(`/mapping/${row.rule_id}/executions/${row.id}`);
      }}
    />
  );
}
