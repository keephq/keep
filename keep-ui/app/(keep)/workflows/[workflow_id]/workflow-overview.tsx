import { useWorkflowExecutionsV2 } from "@/utils/hooks/useWorkflowExecutions";
import { ExclamationCircleIcon } from "@heroicons/react/20/solid";
import { Callout, Title, Card } from "@tremor/react";
import { useSearchParams } from "next/navigation";
import { useState, useEffect } from "react";
import { Workflow } from "@/shared/api/workflows";
import WorkflowGraph from "../workflow-graph";
import { TableFilters } from "./table-filters";
import { ExecutionTable } from "./workflow-execution-table";
import { WorkflowOverviewSkeleton } from "./workflow-overview-skeleton";
import { WorkflowProviders } from "./workflow-providers";
import { WorkflowSteps } from "../mockworkflows";
import { parseWorkflowYamlStringToJSON } from "@/entities/workflows/lib/yaml-utils";
interface Pagination {
  limit: number;
  offset: number;
}

export function StatsCard({ children }: { children: any }) {
  return (
    <Card className="flex flex-col p-4 min-w-1/6 gap-2 justify-between">
      {children}
    </Card>
  );
}

export default function WorkflowOverview({
  workflow: _workflow,
  workflow_id,
}: {
  workflow: Workflow | null;
  workflow_id: string;
}) {
  const [executionPagination, setExecutionPagination] = useState<Pagination>({
    limit: 25,
    offset: 0,
  });
  const searchParams = useSearchParams();

  useEffect(() => {
    setExecutionPagination({
      ...executionPagination,
      offset: 0,
    });
  }, [searchParams]);

  const { data, isLoading, error, isValidating } = useWorkflowExecutionsV2(
    workflow_id,
    executionPagination.limit,
    executionPagination.offset
  );

  if (error) {
    return (
      <Callout
        className="mt-4"
        title="Error"
        icon={ExclamationCircleIcon}
        color="rose"
      >
        Failed to load workflow
      </Callout>
    );
  }

  const parsedWorkflowFile = parseWorkflowYamlStringToJSON(
    data?.workflow?.workflow_raw ?? ""
  );

  const formatNumber = (num: number) => {
    if (num >= 1_000_000) {
      return `${(num / 1_000_000).toFixed(1)}m`;
    } else if (num >= 1_000) {
      return `${(num / 1_000).toFixed(1)}k`;
    } else {
      return num?.toString() ?? "";
    }
  };

  const workflow = {
    last_executions: data?.items,
  } as Pick<Workflow, "last_executions">;

  return (
    <div className="flex flex-col gap-4">
      {/* TODO: Add a working time filter */}
      {(!data || isLoading || isValidating || !workflow) && (
        <WorkflowOverviewSkeleton />
      )}
      {data?.items && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <StatsCard>
              <Title>Total Executions</Title>
              <div>
                <h1 className="text-2xl font-bold">
                  {formatNumber(data.count ?? 0)}
                </h1>
              </div>
            </StatsCard>
            <StatsCard>
              <Title>Pass / Fail Ratio</Title>
              <div>
                <h1 className="text-2xl font-bold">
                  {formatNumber(data.passCount)}
                  {"/"}
                  {formatNumber(data.failCount)}
                </h1>
              </div>
            </StatsCard>
            <StatsCard>
              <Title>Success %</Title>
              <div>
                <h1 className="text-2xl font-bold">
                  {(data.count
                    ? (data.passCount / data.count) * 100
                    : 0
                  ).toFixed(2)}
                  {"%"}
                </h1>
              </div>
            </StatsCard>
            <StatsCard>
              <Title>Avg. Duration</Title>
              <div>
                <h1 className="text-2xl font-bold">
                  {(data.avgDuration ?? 0).toFixed(2)}
                </h1>
              </div>
            </StatsCard>
            <StatsCard>
              <Title>Steps</Title>
              <WorkflowSteps workflow={parsedWorkflowFile} />
            </StatsCard>
          </div>
          <Card>
            <Title>Executions Graph</Title>
            <WorkflowGraph
              showLastExecutionStatus={false}
              workflow={workflow}
              limit={executionPagination.limit}
              showAll={true}
              size="sm"
            />
          </Card>
          <Card>
            <Title>Providers</Title>
            {_workflow && <WorkflowProviders workflow={_workflow} />}
          </Card>
          <h1 className="text-xl font-bold mt-4">Execution History</h1>
          <TableFilters workflowId={data.workflow.id} />
          <ExecutionTable
            executions={data}
            setPagination={setExecutionPagination}
          />
        </div>
      )}
    </div>
  );
}
