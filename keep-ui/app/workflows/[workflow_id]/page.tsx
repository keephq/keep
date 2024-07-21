"use client";
import {
  Callout,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Table,
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
      ? `${apiUrl}/workflows/${params.workflow_id}`
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
      <div className="flex items-center mb-4">
        <Link
          href="/workflows"
          className="flex items-center text-gray-500 hover:text-gray-700"
        >
          <ArrowLeftIcon className="h-5 w-5 mr-1" /> Back to Workflows
        </Link>
      </div>
      {/* Display other workflow details here */}
      {workflowExecutions && (
        <div className="mt-4">
          <h2>Workflow Execution Details Table</h2>
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
                <TableRow key={execution.id}>
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
