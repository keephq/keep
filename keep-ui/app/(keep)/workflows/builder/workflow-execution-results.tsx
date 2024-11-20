"use client";
import React, { useEffect, useRef, useState } from "react";
import {
  Accordion,
  AccordionBody,
  AccordionHeader,
  Card,
  Title,
} from "@tremor/react";
import { useSession } from "next-auth/react";
import { useApiUrl } from "utils/hooks/useConfig";
import Loading from "../../../loading";
import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import {
  Callout,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
} from "@tremor/react";
import useSWR from "swr";
import { fetcher } from "../../../../utils/fetcher";
import {
  WorkflowExecution,
  WorkflowExecutionFailure,
  isWorkflowExecution,
} from "./types";

interface WorkflowResultsProps {
  workflow_id: string;
  workflow_execution_id: string;
}

export default function WorkflowExecutionResults({
  workflow_id,
  workflow_execution_id,
}: WorkflowResultsProps) {
  const apiUrl = useApiUrl();
  const { data: session, status, update } = useSession();
  const [refreshInterval, setRefreshInterval] = useState(1000);
  const [checks, setChecks] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const { data: executionData, error: executionError } = useSWR(
    status === "authenticated"
      ? `${apiUrl}/workflows/${workflow_id}/runs/${workflow_execution_id}`
      : null,
    async (url) => {
      const fetchedData = await fetcher(url, session?.accessToken!);
      if (fetchedData.status === "in_progress") {
        setChecks((c) => c + 1);
      }
      return fetchedData;
    },
    {
      refreshInterval: refreshInterval,
    }
  );

  // disable refresh interval when execution is complete
  useEffect(() => {
    if (!executionData) return;

    // if the status is other than in_progress, stop the refresh interval
    if (executionData?.status !== "in_progress") {
      console.log("Stopping refresh interval");
      setRefreshInterval(0);
    }
    // if there's an error - show it
    if (executionData.error) {
      setError(executionData?.error);
      console.log("Stopping refresh interval");
      setRefreshInterval(0);
    } else if (executionData?.status === "success") {
      setError(executionData?.error); // should be null
      setRefreshInterval(0); // Disable refresh interval when execution is complete
    }
  }, [executionData]);

  if (executionError) {
    console.error("Error fetching execution status", executionError);
  }

  if (status === "loading" || !executionData) return <Loading />;

  if (executionError) {
    return (
      <Callout
        className="mt-4"
        title="Error"
        icon={ExclamationCircleIcon}
        color="rose"
      >
        Failed to load workflow execution
      </Callout>
    );
  }

  return (
    <ExecutionResults
      executionData={executionData}
      checks={checks}
    ></ExecutionResults>
  );
}

export function ExecutionResults({
  executionData,
  checks,
}: {
  executionData: WorkflowExecution | WorkflowExecutionFailure;
  checks?: number;
}) {
  let status: WorkflowExecution["status"] | undefined;
  let logs: WorkflowExecution["logs"] | undefined;
  let results: WorkflowExecution["results"] | undefined;

  const error = executionData.error;

  if (isWorkflowExecution(executionData)) {
    status = executionData.status;
    logs = executionData.logs;
    results = executionData.results;
  }

  return (
    <div>
      {results && Object.keys(results).length > 0 && (
        <Card>
          <Title>Workflow Results</Title>
          <Table className="w-full">
            <TableHead>
              <TableRow>
                <TableCell className="w-1/4 break-words whitespace-normal">
                  Action ID
                </TableCell>
                <TableCell className="w-3/4 break-words whitespace-normal">
                  Results
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {Object.entries(results).map(([stepId, stepResults], index) => (
                <TableRow key={index}>
                  <TableCell className="w-1/4 break-words whitespace-normal">
                    {stepId}
                  </TableCell>
                  <TableCell className="w-3/4 break-words whitespace-normal max-w-xl">
                    <Accordion>
                      <AccordionHeader>Value</AccordionHeader>
                      <AccordionBody>
                        <pre className="overflow-scroll">
                          {JSON.stringify(stepResults, null, 2)}
                        </pre>
                      </AccordionBody>
                    </Accordion>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
      <div className={results && Object.keys(results).length > 0 ? "mt-8" : ""}>
        {status === "in_progress" ? (
          <div>
            <div className="flex items-center justify-center">
              <p>
                The workflow is in progress, will check again in one second
                (times checked: {checks})
              </p>
            </div>
            <Loading></Loading>
          </div>
        ) : (
          <>
            {error && (
              <Callout
                className="mt-4 mb-2.5"
                title="Error during workflow execution"
                icon={ExclamationCircleIcon}
                color="rose"
              >
                {error
                  ? error.split("\n").map((line, index) => (
                      // Render each line as a separate paragraph or div.
                      // The key is index, which is sufficient for simple lists like this.
                      <p key={index}>{line}</p>
                    ))
                  : "An unknown error occurred during execution."}
              </Callout>
            )}
            <Card>
              <Title>Workflow Logs</Title>
              <Table className="w-full">
                <TableHead>
                  <TableRow>
                    <TableCell className="w-1/3 break-words whitespace-normal">
                      Timestamp
                    </TableCell>
                    <TableCell className="w-1/3 break-words whitespace-normal">
                      Message
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(logs ?? []).map((log, index) => (
                    <TableRow
                      className={`${
                        log.message?.includes("NOT to run")
                          ? "bg-red-100"
                          : log.message?.includes("evaluated to run")
                          ? "bg-green-100"
                          : ""
                      }`}
                      key={index}
                    >
                      <TableCell className="w-1/3 break-words whitespace-normal">
                        {log.timestamp}
                      </TableCell>
                      <TableCell className="w-1/3 break-words whitespace-normal">
                        {log.message}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
