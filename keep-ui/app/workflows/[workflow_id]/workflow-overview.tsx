import { useWorkflowExecutionsV2 } from "@/utils/hooks/useWorkflowExecutions";
import { useWorkflowRun } from "@/utils/hooks/useWorkflowRun";
import { ExclamationCircleIcon } from "@heroicons/react/20/solid";
import { Callout, Button, Title, Card, Tab, TabGroup, TabList } from "@tremor/react";
import { load, JSON_SCHEMA } from "js-yaml";
import { useSearchParams } from "next/navigation";
import { useState, useEffect, Dispatch, SetStateAction, useLayoutEffect } from "react";
import Loading from "app/loading";
import { WorkflowSteps } from "../mockworkflows";
import { Workflow } from "../models";
import WorkflowGraph from "../workflow-graph";
import AlertTriggerModal from "../workflow-run-with-alert-modal";
import { TableFilters } from "./table-filters";
import { ExecutionTable } from "./workflow-execution-table";
import { PaginatedWorkflowExecutionDto } from "../builder/types";

interface Pagination {
  limit: number;
  offset: number;
}

const tabs = [
  { name: "All Time", value: "alltime" },
  { name: "Last 30d", value: "last_30d" },
  { name: "Last 7d", value: "last_7d" },
  { name: "Today", value: "today" },
];

export function StatsCard({
    children,
    data,
  }: {
    children: any;
    data?: string;
  }) {
    return (
      <Card className="group relative container flex flex-col p-4 space-y-2 min-w-1/5">
        {!!data && (
          <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 hidden group-hover:block bg-gray-800 text-white rounded py-1 p-2 text-2xl font-bold">
            {data}
          </div>
        )}
        {children}
      </Card>
    );
  }

export const FilterTabs = ({
    tabs,
    setTab,
    tab,
  }: {
    tabs: { name: string; value: string }[];
    setTab: Dispatch<SetStateAction<number>>;
    tab: number;
  }) => {
    return (
      <div className="max-w-lg space-y-12 pt-6">
        <TabGroup
          index={tab}
          onIndexChange={(index: number) => {
            setTab(index);
          }}
        >
          <TabList variant="solid" color="black" className="bg-gray-300">
            {tabs.map((tabItem, index) => (
              <Tab key={tabItem.value}>{tabItem.name}</Tab>
            ))}
          </TabList>
        </TabGroup>
      </div>
    );
  };
export default function WorkflowOverview({
  workflow_id,
}: {
  workflow_id: string;
}) {
  const [executionPagination, setExecutionPagination] = useState<Pagination>({
    limit: 25,
    offset: 0,
  });
  const [tab, setTab] = useState<number>(1);
  const searchParams = useSearchParams();

  useEffect(() => {
    setExecutionPagination({
      ...executionPagination,
      offset: 0,
    });
  }, [tab, searchParams]);

  const { data, isLoading, error, isValidating } = useWorkflowExecutionsV2(
    workflow_id,
    tab,
    executionPagination.limit,
    executionPagination.offset
  );

  const {
    isRunning,
    handleRunClick,
    getTriggerModalProps,
    isRunButtonDisabled,
    message,
  } = useWorkflowRun(data?.workflow!);


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

  const parsedWorkflowFile = load(data?.workflow?.workflow_raw ?? "", {
    schema: JSON_SCHEMA,
  }) as any;

  const formatNumber = (num: number) => {
    if (num >= 1_000_000) {
      return `${(num / 1_000_000).toFixed(1)}m`;
    } else if (num >= 1_000) {
      return `${(num / 1_000).toFixed(1)}k`;
    } else {
      return num?.toString() ?? "";
    }
  };

  const workflow = { last_executions: data?.items } as Partial<Workflow>;

  return (
    <>
      <div className="sticky top-0 flex justify-between items-end">
        <div className="flex-1">
          {/*TO DO update searchParams for these filters*/}
          <FilterTabs tabs={tabs} setTab={setTab} tab={tab} />
        </div>
        {!!data?.workflow && (
          <Button
            disabled={isRunning || isRunButtonDisabled}
            className="p-2 px-4"
            onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
              e.stopPropagation();
              e.preventDefault();
              handleRunClick?.();
            }}
            tooltip={message}
          >
            Run now
          </Button>
        )}
      </div>
      {!data || isLoading || isValidating && <Loading />}
      {data?.items && (
        <div className="mt-2 flex flex-col gap-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 p-0.5">
            <StatsCard data={`${data.count ?? 0}`}>
              <Title>Total Executions</Title>
              <div>
                <h1 className="text-2xl font-bold">
                  {formatNumber(data.count ?? 0)}
                </h1>
              </div>
            </StatsCard>
            <StatsCard data={`${data.passCount}/${data.failCount}`}>
              <Title>Pass / Fail ratio</Title>
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
              <Title>Avg. duration</Title>
              <div>
                <h1 className="text-2xl font-bold">
                  {(data.avgDuration ?? 0).toFixed(2)}
                </h1>
              </div>
            </StatsCard>
            <StatsCard>
              <Title>Involved Services</Title>
              <WorkflowSteps workflow={parsedWorkflowFile} />
            </StatsCard>
          </div>
          <WorkflowGraph
            showLastExecutionStatus={false}
            workflow={workflow}
            limit={executionPagination.limit}
            showAll={true}
            size="sm"
          />
          <h1 className="text-xl font-bold mt-4">Execution History</h1>
          <TableFilters workflowId={data.workflow.id} />
          <ExecutionTable
            executions={data}
            setPagination={setExecutionPagination}
          />
        </div>
      )}
      {!!data?.workflow && !!getTriggerModalProps && (
        <AlertTriggerModal {...getTriggerModalProps()} />
      )}
    </>
  );
}
