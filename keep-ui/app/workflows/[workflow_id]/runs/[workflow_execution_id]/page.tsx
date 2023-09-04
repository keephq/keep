'use client';
import React, { useEffect, useState } from 'react';
import { useSession } from '../../../../../utils/customAuth';
import { getApiURL } from '../../../../../utils/apiUrl';
import Loading from '../../../../loading';
import { ExclamationCircleIcon, CheckCircleIcon } from '@heroicons/react/24/outline';
import { Callout, Table, TableBody, TableCell, TableHead, TableRow } from '@tremor/react';
import useSWR from 'swr';
import { fetcher } from '../../../../../utils/fetcher';


interface LogEntry {
  timestamp: string;
  message: string;
}

export default function WorkflowExecutionPage({ params }: { params: { workflow_id: string, workflow_execution_id: string } }) {

  const apiUrl = getApiURL();
  const { data: session, status, update } = useSession();
  const [refreshInterval, setRefreshInterval] = useState(1000);
  const [checks, setChecks] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const { data: executionData, error: executionError } = useSWR(
    status === 'authenticated'
      ? `${apiUrl}/workflows/${params.workflow_id}/runs/${params.workflow_execution_id}`
      : null,
    async (url) => {
      const fetchedData = await fetcher(url, session?.accessToken!);
      if (fetchedData.status === 'in_progress') {
        setChecks(c => c + 1);
      }
      return fetchedData;
    },
    {
      refreshInterval: refreshInterval
    }
  );

  // disable refresh interval when execution is complete
  useEffect(() => {
    if (!executionData) return;

    // if the status is other than in_progress, stop the refresh interval
    if (executionData?.status !== 'in_progress') {
      console.log("Stopping refresh interval");
      setRefreshInterval(0);
    }
    // if there's an error - show it
    if(executionData?.error){
      setError(executionData?.error);
      console.log("Stopping refresh interval");
      setRefreshInterval(0);
    }
  }, [executionData]);

  if (executionError) {
    console.error('Error fetching execution status', executionError);
  }

  const executionStatus = executionData?.status;
  const logs = executionData?.logs || [];

  if (status === 'loading' || !executionData) return <Loading />;

  if (executionError) {
    return (
      <Callout className="mt-4" title="Error" icon={ExclamationCircleIcon} color="rose">
        Failed to load workflow execution
      </Callout>
    );
  }

  return (
    <div>
      {executionStatus === 'success' ? (
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Timestamp</TableCell>
              <TableCell>Message</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {logs.map((log: any, index: any) => (
              <TableRow key={index}>
                <TableCell>{log.timestamp}</TableCell>
                <TableCell>{log.message}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : executionStatus === 'in_progress' ? (
        <div>
           <div className="flex items-center justify-center">
             <p>The workflow is in progress, will check again in one second (times checked: {checks})</p>
           </div>
           <Loading></Loading>
        </div>
      ) : (
        <Callout className="mt-4" title="Error during workflow exceution" icon={ExclamationCircleIcon} color="rose">
          {error || 'An unknown error occurred during execution.'}
        </Callout>

      )}
    </div>
  );
}
