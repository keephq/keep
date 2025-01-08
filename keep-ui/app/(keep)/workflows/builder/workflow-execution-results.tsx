"use client";

import React, { useEffect, useState } from "react";
import { Card, Title, Button } from "@tremor/react";
import Loading from "@/app/(keep)/loading";
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
import {
  WorkflowExecution,
  WorkflowExecutionFailure,
  isWorkflowExecution,
} from "./types";
import { useApi } from "@/shared/lib/hooks/useApi";
import WorkflowDefinitionYAML from "../workflow-definition-yaml";

interface WorkflowResultsProps {
  workflow_id: string;
  workflow_execution_id: string;
}

export default function WorkflowExecutionResults({
  workflow_id,
  workflow_execution_id,
}: WorkflowResultsProps) {
  const api = useApi();
  const [refreshInterval, setRefreshInterval] = useState(1000);
  const [checks, setChecks] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const { data: executionData, error: executionError } = useSWR(
    api.isReady()
      ? `/workflows/${workflow_id}/runs/${workflow_execution_id}`
      : null,
    async (url) => {
      const fetchedData = await api.get(url);
      if (fetchedData.status === "in_progress") {
        setChecks((c) => c + 1);
      }
      return fetchedData;
    },
    {
      refreshInterval: refreshInterval,
    }
  );

  // Get workflow definition
  const { data: workflowData, error: workflowError } = useSWR(
    api.isReady() ? `/workflows/${workflow_id}` : null,
    (url) => api.get(url)
  );

  console.log("workflowData", workflowData);

  useEffect(() => {
    if (!executionData) return;

    if (executionData?.status !== "in_progress") {
      console.log("Stopping refresh interval");
      setRefreshInterval(0);
    }
    if (executionData.error) {
      setError(executionData?.error);
      console.log("Stopping refresh interval");
      setRefreshInterval(0);
    } else if (executionData?.status === "success") {
      setError(executionData?.error);
      setRefreshInterval(0);
    }
  }, [executionData]);

  if (executionError) {
    console.error("Error fetching execution status", executionError);
  }

  if (!executionData || !workflowData) return <Loading />;

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

  if (workflowError) {
    return (
      <Callout title="Error" icon={ExclamationCircleIcon} color="rose">
        Failed to load workflow definition
      </Callout>
    );
  }

  return (
    <ExecutionResults
      workflowId={workflow_id}
      executionData={executionData}
      workflowRaw={workflowData.workflow_raw}
      checks={checks}
    />
  );
}

export function ExecutionResults({
  workflowId,
  executionData,
  workflowRaw,
  checks,
}: {
  executionData: WorkflowExecution | WorkflowExecutionFailure;
  workflowId: string | undefined;
  workflowRaw: string | undefined;
  checks?: number;
}) {
  const api = useApi();

  let status: WorkflowExecution["status"] | undefined;
  let logs: WorkflowExecution["logs"] | undefined;
  let results: WorkflowExecution["results"] | undefined;
  let eventId: string | undefined;
  let eventType: string | undefined;

  const error = executionData.error;

  if (isWorkflowExecution(executionData)) {
    status = executionData.status;
    logs = executionData.logs;
    results = executionData.results;
    eventId = executionData.event_id;
    eventType = executionData.event_type;
  }

  const getCurlCommand = () => {
    let token = api.getToken();
    let url = api.getApiBaseUrl();
    // Only include workflow ID if workflowData is available
    const workflowIdParam = workflowId ? `/${workflowId}` : "";
    return `curl -X POST "${url}/workflows${workflowIdParam}/run?event_type=${eventType}&event_id=${eventId}" \\
  -H "Authorization: Bearer ${token}" \\
  -H "Content-Type: application/json"`;
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(getCurlCommand());
  };

  return (
    <div className="flex flex-col gap-4 h-[calc(100vh-8rem)]">
      {/* Error Card */}
      {error && (
        <Callout
          title="Error during workflow execution"
          icon={ExclamationCircleIcon}
          color="rose"
        >
          <div className="flex justify-between items-center">
            <div>
              {error.split("\n").map((line, index) => (
                <p key={index}>{line}</p>
              ))}
            </div>
            {eventId && eventType && (
              <Button color="rose" onClick={copyToClipboard}>
                Copy CURL replay
              </Button>
            )}
          </div>
        </Callout>
      )}

      {/* Workflow Results Card */}
      {/*
      <Card className="flex-none overflow-hidden">
        <div className="overflow-auto">
          {results && Object.keys(results).length > 0 && (
            <div className="mb-4">
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
                            <pre className="overflow-auto max-h-48">
                              {JSON.stringify(stepResults, null, 2)}
                            </pre>
                          </AccordionBody>
                        </Accordion>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </Card>
      */}

      {/* Lower Section with Logs and Definition */}
      <div className="grid grid-cols-2 gap-4 flex-1">
        {/* Workflow Logs Card */}
        <Card className="flex flex-col overflow-hidden">
          <div className="flex-1 overflow-auto">
            {status === "in_progress" ? (
              <div>
                <div className="flex items-center justify-center">
                  <p>
                    The workflow is in progress, will check again in one second
                    (times checked: {checks})
                  </p>
                </div>
                <Loading />
              </div>
            ) : (
              <div>
                <Title>Workflow Logs</Title>
                <Table className="w-full">
                  <TableHead>
                    <TableRow>
                      <TableCell className="w-1/3 break-words whitespace-normal">
                        Timestamp
                      </TableCell>
                      <TableCell className="w-2/3 break-words whitespace-normal">
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
                        <TableCell className="w-2/3 break-words whitespace-normal">
                          {log.message}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </Card>

        {/* Workflow Definition Card */}
        <Card className="flex flex-col overflow-hidden">
          <Title>Workflow Definition</Title>
          <div className="flex-1 mt-4 overflow-auto">
            <WorkflowDefinitionYAML
              workflowRaw={workflowRaw ?? ""}
              executionLogs={logs}
              executionStatus={status}
            />
          </div>
        </Card>
      </div>
    </div>
  );
}
