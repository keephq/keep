'use client';
import React, { useEffect, useRef, useState } from 'react';
import { useSession } from '../../../../../utils/customAuth';
import { getApiURL } from '../../../../../utils/apiUrl';
import Loading from '../../../../loading';
import { ExclamationCircleIcon, DocumentTextIcon, ChevronDoubleDownIcon, ChevronDoubleRightIcon } from '@heroicons/react/24/outline';
import { Callout, Icon, Table, TableBody, TableCell, TableHead, TableRow } from '@tremor/react';
import useSWR from 'swr';
import { fetcher } from '../../../../../utils/fetcher';


interface LogEntry {
  timestamp: string;
  message: string;
  context: string;
}

export default function WorkflowExecutionPage({ params }: { params: { workflow_id: string, workflow_execution_id: string } }) {

  const apiUrl = getApiURL();
  const { data: session, status, update } = useSession();
  const [refreshInterval, setRefreshInterval] = useState(1000);
  const [checks, setChecks] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({});
  const contentRef = useRef<(HTMLDivElement | null)[]>([]);



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
    else {
      setError(executionData?.error);
      setRefreshInterval(0); // Disable refresh interval when execution is complete
    }
  }, [executionData]);

  if (executionError) {
    console.error('Error fetching execution status', executionError);
  }

  const executionStatus = executionData?.status;
  const logs = executionData?.logs as [LogEntry]|| [];

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
          <Table className="w-full">
          <TableHead>
            <TableRow>
              <TableCell className="w-1/3 break-words whitespace-normal">Timestamp</TableCell>
              <TableCell className="w-1/3 break-words whitespace-normal">Message</TableCell>
              <TableCell className="w-1/3 break-words whitespace-normal">Context</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {logs.map((log, index) => (
              <TableRow key={index}>
                <TableCell className="w-1/3 break-words whitespace-normal">{log.timestamp}</TableCell>
                <TableCell className="w-1/3 break-words whitespace-normal">{log.message}</TableCell>
                <TableCell
                  className="w-1/3 break-words whitespace-normal cursor-pointer"
                  onClick={() => {
                    if (contentRef.current[index] && expandedRows[index]) {
                      contentRef.current[index]!.style.maxHeight = '6rem'; // Matches max-h-24
                    } else if (contentRef.current[index]) {
                        contentRef.current[index]!.style.maxHeight = `${contentRef.current[index]!.scrollHeight}px`;
                    }
                    setExpandedRows(prevState => ({ ...prevState, [index]: !prevState[index] }));
                  }}
                >
                  <div className="flex items-start justify-between">
                    <div
                      ref={el => contentRef.current[index] = el}
                      className={`overflow-hidden transition-max-height duration-300 ${expandedRows[index] ? 'max-h-screen' : 'max-h-24'}`}>
                      <pre className="whitespace-pre-wrap">{JSON.stringify(log.context, null, 2)}</pre>
                    </div>
                    <button
                      className="ml-4 mt-8"
                      onClick={(e) => {
                        e.stopPropagation();  // prevent the TableCell click event from being triggered
                        setExpandedRows(prevState => ({ ...prevState, [index]: !prevState[index] }));
                      }}
                    >
                      <Icon
                        icon={ChevronDoubleRightIcon}
                        color="orange"
                        size="lg"
                        className="grayscale hover:grayscale-0"
                        tooltip="Show more"
                      />
                    </button>
                  </div>
                </TableCell>

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
