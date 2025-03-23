import { createColumnHelper, DisplayColumnDef } from "@tanstack/react-table";
import { GenericTable } from "@/components/table/GenericTable";
import {
  EnrichmentEvent,
  PaginatedEnrichmentExecutionDto,
} from "@/shared/api/enrichment-events";
import { Dispatch, SetStateAction } from "react";
import { useRouter } from "next/navigation";
import { getIcon } from "../../app/(keep)/workflows/[workflow_id]/workflow-execution-table";
import TimeAgo from "react-timeago";
import { formatDistanceToNowStrict } from "date-fns";

interface Pagination {
  limit: number;
  offset: number;
}

interface Props {
  executions: PaginatedEnrichmentExecutionDto;
  setPagination: Dispatch<SetStateAction<Pagination>>;
}

export function ExecutionsTable({ executions, setPagination }: Props) {
  const columnHelper = createColumnHelper<EnrichmentEvent>();
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
      id: "started",
      header: "Started",
      cell: ({ row }) => (
        <TimeAgo
          date={row.original.timestamp + "Z"}
          formatter={(value, unit, suffix) => {
            if (!row.original.timestamp) return "";
            return formatDistanceToNowStrict(
              new Date(row.original.timestamp + "Z"),
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
  ] as DisplayColumnDef<EnrichmentEvent>[];

  return (
    <GenericTable<EnrichmentEvent>
      data={executions.items}
      columns={columns}
      rowCount={executions.count}
      offset={executions.offset}
      limit={executions.limit}
      onPaginationChange={(newLimit: number, newOffset: number) =>
        setPagination({ limit: newLimit, offset: newOffset })
      }
      onRowClick={(row: EnrichmentEvent) => {
        router.push(`/mapping/${row.rule_id}/executions/${row.id}`);
      }}
    />
  );
}
