"use client";
import {
  Callout,
  Card,
  Title,
  Tab,
  TabGroup,
  TabList,
} from "@tremor/react";
import Link from "next/link";
import React, { Dispatch, SetStateAction, useState } from "react";
import { MdModeEdit } from "react-icons/md";
import { getApiURL } from "../../../utils/apiUrl";
import { useSession } from "next-auth/react";
import {
  ExclamationCircleIcon,
  PlayIcon,
} from "@heroicons/react/24/outline";
import Loading from "../../loading";
import { useRouter } from "next/navigation";
import { WorkflowExecution, PaginatedWorkflowExecutionDto } from "../builder/types";
import { useWorkflowExecutionsV2 } from "utils/hooks/useWorkflowExecutions";
import { GenericTable } from "@/components/table/GenericTable"
import { ExecutionResults } from '../builder/workflow-execution-results';

import {
  createColumnHelper,
  DisplayColumnDef,
} from "@tanstack/react-table";
import WorkflowGraph from "../workflow-graph";
import { Workflow } from '../models';
import { useWorkflows } from "utils/hooks/useWorkflows";
// import { WorkflowSteps } from "../mockworkflows";
const tabs = [
  { name: "All Time", value: 'alltime' },
  { name: "Last 30d", value:"last_30d" },
  { name: "Last 7d", value: "last_7d" },
  { name: "Today", value: "today" },
];

export const FilterTabs = ({
  tabs,
  setTab,
  tab
}: {
  tabs: { name: string; value: string }[];
  setTab: Dispatch<SetStateAction<number>>;
  tab: number;
}) => {

  return (
    <div className="absolute top-0 left-0 max-w-lg space-y-12 pt-6 sticky top-0">
      <TabGroup
       index={tab}
       onIndexChange={(index: number) =>{setTab(index)}}
      >
        <TabList variant="solid" color="black" className="bg-gray-300">
          {tabs.map((tabItem, index) => (
            <Tab
              key={tabItem.value}
            >
              {tabItem.name}
            </Tab>
          ))}
        </TabList>
      </TabGroup>
    </div>
  );
};


const columnHelper = createColumnHelper<WorkflowExecution>();

interface Props {
  executions: PaginatedWorkflowExecutionDto;
  // mutate: () => void;
  setPagination: Dispatch<SetStateAction<any>>;
  // editCallback: (rule: IncidentDto) => void;
}


export function StatsCard({ children }:{children:any}) {
  return <Card className="w-1/4 flex flex-col p-4 space-y-2">
    {children}
  </Card>
}

export function ExecutionTable({
  executions,
  setPagination,
  // mutate,
  // editCallback,
}: Props) {
  const { data: session } = useSession();

  const columns = [
    columnHelper.display({
      id: "started",
      header: "Started",
      cell: ({ row }) =>
        new Date(row.original.started + "Z").toLocaleString(),
    }),
    columnHelper.accessor("id", {
      header: "Execution ID",
    }),
    columnHelper.accessor("triggered_by", {
      header: "Trigger",
    }),
    columnHelper.accessor("status", {
      header: "Status",
    }),
    columnHelper.display({
      id: "error",
      header: "Error",
      cell: ({ row }) => (
        <div className="max-w-xl truncate" title={row.original.error || ""}>
          {row.original.error}
        </div>
      ),
    }),
    columnHelper.accessor("execution_time", {
      header: "Execution time",
    }),
    columnHelper.display({
      id: "logs",
      header: "Logs",
      cell: ({ row }) => (
        <Link
          className="text-orange-500 hover:underline flex items-center"
          href={`/workflows/${row.original.workflow_id}/runs/${row.original.id}`}
          passHref
        >
          <PlayIcon className="h-4 w-4 ml-1" />
        </Link>
      ),
    }),
  ] as DisplayColumnDef<WorkflowExecution>[];


  return <GenericTable<WorkflowExecution>
    data={executions.items}
    columns={columns}
    rowCount={executions.count ?? 0} // Assuming pagination is not needed, you can adjust this if you have pagination
    offset={executions.offset} // Customize as needed
    limit={executions.limit} // Customize as needed
    onPaginationChange={setPagination}
  />

}


interface Pagination {
  limit: number;
  offset: number;
}

export default function WorkflowDetailPage({
  params,
}: {
  params: { workflow_id: string };
}) {
  const columnHelper = createColumnHelper<WorkflowExecution>();
  const apiUrl = getApiURL();
  const router = useRouter();
  const { data: session, status, update } = useSession();
   const { data: workflows } = useWorkflows();
  const workflowData = workflows?.find((wf) => wf.id === params.workflow_id);

  const [executionPagination, setExecutionPagination] = useState<Pagination>({
    limit: 20,
    offset: 0,
  });
  const [tab, setTab] = useState<number>(1)

  const {
    data,
    isLoading,
    error
  } = useWorkflowExecutionsV2(params.workflow_id, tab, executionPagination.limit, executionPagination.offset);

 
  if (isLoading || !data) return <Loading />;

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
  if (status === "loading" || isLoading || !data) return <Loading />;
  if (status === "unauthenticated") router.push("/signin");

  // const workflowExecutions = data?.items.sort((a, b) => {
  //   return new Date(b.started).getTime() - new Date(a.started).getTime();
  // });


  
  const workflow = { last_executions: workflowExecutions } as Partial<Workflow>
console.log("tab=======>", tab);
  return (
    <div className="relative">
      <FilterTabs tabs={tabs} setTab={setTab} tab={tab}/>
      {/* Display other workflow details here */}
      {data?.items && (
        <div className="mt-2 flex flex-col gap-2">
          <div className="flex justify-between items-center p-2 gap-8">
            <StatsCard>
              <Title>
                Total Executions
              </Title>
              <div>
                <h1 className="text-2xl font-bold">{executions.total ?? 0}</h1>
                <div className="text-sm text-gray-500">__ from last month</div>
              </div>
            </StatsCard>
            <StatsCard>
            <Title>
                Pass / Fail ratio
              </Title>
              <div>
                <h1 className="text-2xl font-bold">{executions.passFail ?? 0}</h1>
                <div className="text-sm text-gray-500">__ from last month</div>
              </div>
              
            </StatsCard>
            <StatsCard>
            <Title>
                Avg. duration
              </Title>
              <div>
                <h1 className="text-2xl font-bold">{executions.avgDuration ?? 0}</h1>
                <div className="text-sm text-gray-500">__ from last month</div>
              </div>
              
            </StatsCard>
            <StatsCard>
            <Title>
                Invloved Services
              </Title>
              {/* <WorkflowSteps workflow={workflowData!} /> */}
            </StatsCard>
          </div>
          <WorkflowGraph workflow={workflow} limit={executionPagination.limit} showAll={true} size="sm" />

          <h1 className="text-xl font-bold mt-4">Execution History</h1>
          <ExecutionTable
            executions={data}
            // mutate={mutateExecutions}
            setPagination={setExecutionPagination}
          // editCallback={handleStartEdit}
          />
          {/* <Table>
        <TableHead>
              <TableRow>
                <TableHeaderCell>Started</TableHeaderCell>
                <TableHeaderCell>Execution ID</TableHeaderCell>
                <TableHeaderCell>Trigger</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell>Error</TableHeaderCell>
                <TableHeaderCell>Execution time</TableHeaderCell>
                <TableHeaderCell>Logs</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {workflowExecutions.map((execution) => (
                <TableRow key={execution.id} className="hover:bg-orange-100 cursor-pointer">
                  <TableCell>
                    {new Date(execution.started + "Z").toLocaleString()}
                  </TableCell>
                  <TableCell>{execution.id}</TableCell>
                  <TableCell>{execution.triggered_by}</TableCell>
                  <TableCell>{execution.status}</TableCell>
                  <TableCell
                    className="max-w-xl truncate"
                    title={execution.error ? execution.error : ""}
                  >
                    {execution.error}
                  </TableCell>
                  <TableCell>{execution.execution_time}</TableCell>
                  <TableCell>
                    <Link
                      className="text-orange-500 hover:underline flex items-center"
                      href={`/workflows/${execution.workflow_id}/runs/${execution.id}`}
                      passHref
                    >
                      <PlayIcon className="h-4 w-4 ml-1" />
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table> */}
        </div>
      )}
    </div>
  );
}
