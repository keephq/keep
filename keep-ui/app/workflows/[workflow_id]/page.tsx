"use client";
import {
  Callout,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Table,
  Card,
  Title,
  Tab,
  TabGroup,
  TabList,
} from "@tremor/react";
import Link from "next/link";
import React, { useState } from "react";
import { getApiURL } from "../../../utils/apiUrl";
import { useSession } from "next-auth/react";
import useSWR from "swr";
import { fetcher } from "../../../utils/fetcher";
import {
  ExclamationCircleIcon,
  ArrowLeftIcon,
  PlayIcon,
} from "@heroicons/react/24/outline";
import Loading from "../../loading";
import { useRouter } from "next/navigation";
import { WorkflowExecution } from "../builder/types";
const tabs=[
  {name: "All Time"},
  {name: "Last 30d"},
  {name: "Last 7d"},
  {name: "Today"},
  ];

export const FilterTabs = ({
  tabs,
}: {
  tabs: { name: string; onClick?: () => void }[];
}) => (
  <div className="max-w-lg space-y-12 pt-6 sticky top-0">
    <TabGroup>
      <TabList 
      variant="solid" 
      color="black"
       className="bg-gray-300"
      >
        {tabs?.map(
          (tab: { name: string; onClick?: () => void }, index: number) => (
            <Tab key={index} value={tab.name}>
              {tab.name}
            </Tab>
          )
        )}
      </TabList>
    </TabGroup>
  </div>
);



export default function WorkflowDetailPage({
  params,
}: {
  params: { workflow_id: string };
}) {
  const apiUrl = getApiURL();
  const router = useRouter();
  const { data: session, status, update } = useSession();

  const { data, error, isLoading } = useSWR<WorkflowExecution[]>(
    status === "authenticated"
      ? `${apiUrl}/workflows/${params.workflow_id}?v2=true`
      : null,
    (url: string) => fetcher(url, session?.accessToken!)
  );

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

  const workflowExecutions = data.sort((a, b) => {
    return new Date(b.started).getTime() - new Date(a.started).getTime();
  });

  return (
    <div>
      <FilterTabs tabs={tabs}/>
      {/* Display other workflow details here */}
      {workflowExecutions && (
        <div className="mt-4 flex gap-2">
          {/* <h2>Workflow Execution Details Table</h2> */}
          {/* <SideNavBar /> */}
          {/* <Table className="flex-grow mt-4 overflow-auto [&>table]:table-fixed [&>table]:w-full">
          <WorkflowTableHeaders
            columns={columns}
            table={table}
            presetName={presetName}
          />
          <AlertsTableBody
            table={table}
            showSkeleton={showSkeleton}
            showEmptyState={showEmptyState}
            theme={theme}
            onRowClick={handleRowClick}
            presetName={presetName}
          />
        </Table> */}
        <Table>
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
          </Table>
        </div>
      )}
    </div>
  );
}
