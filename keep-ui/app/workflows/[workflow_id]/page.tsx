'use client';
import { Callout, TableBody, TableCell, TableHead, TableHeaderCell, TableRow, Table} from '@tremor/react';
import Link from 'next/link';
import React, { useState } from 'react';
import { getApiURL } from '../../../utils/apiUrl';
import { useSession } from '../../../utils/customAuth';
import useSWR from 'swr';
import { fetcher } from '../../../utils/fetcher';
import { ExclamationCircleIcon, ArrowLeftIcon } from '@heroicons/react/24/outline';
import Loading from '../../loading';

interface WorkflowExecution {
  id: string;
  workflow_id: string;
  tenant_id: string;
  started: string;
  triggered_by: string;
  status: string;
  logs?: string | null;
  error?: string | null;
  execution_time?: number | null;
}

export default function WorkflowDetailPage({ params }: { params: { workflow_id: string } }){

  const apiUrl = getApiURL();
  const { data: session, status, update } = useSession();

  const { data, error, isLoading } = useSWR<WorkflowExecution[]>(
      `${apiUrl}/workflows/${params.workflow_id}`,
      (url) => fetcher(url, session?.accessToken!)
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
  if (status === "loading" || isLoading || !data) return <Loading />;
  if (status === "unauthenticated") return <div>Unauthenticated...</div>;

  const workflowExecutions = data;

  return (
    <div>
       <div className="flex items-center mb-4">
        <Link href="/workflows" className="flex items-center text-gray-500 hover:text-gray-700">
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
              </TableRow>
            </TableHead>
            <TableBody>
              {workflowExecutions.map((execution) => (
                <TableRow key={execution.id}>
                  <TableCell>{execution.started}</TableCell>
                  <TableCell>{execution.id}</TableCell>
                  <TableCell>{execution.triggered_by}</TableCell>
                  <TableCell>{execution.status}</TableCell>
                  <TableCell>{execution.error}</TableCell>
                  <TableCell>{execution.execution_time}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
};
