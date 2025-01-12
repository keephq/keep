"use client";

import React, { useEffect, useState } from "react";
import { Card, Title } from "@tremor/react";
import Loading from "@/app/(keep)/loading";
import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { Callout } from "@tremor/react";
import useSWR from "swr";
import {
  WorkflowExecutionDetail,
  WorkflowExecutionFailure,
  isWorkflowExecution,
} from "@/shared/api/workflow-executions";
import { useApi } from "@/shared/lib/hooks/useApi";
import { WorkflowDefinitionYAML } from "./WorkflowDefinitionYAML";
import { WorkflowExecutionError } from "./WorkflowExecutionError";
import { WorkflowExecutionLogs } from "./WorkflowExecutionLogs";
import { setFavicon } from "@/shared/ui/utils/favicon";

const getStatusEmoji = (status: WorkflowExecutionDetail["status"]) => {
  if (status === "success") return "✔";
  if (status === "failed") return "✗";
  if (status === "in_progress") return "○";
  return "";
};

const convertWorkflowStatusToFaviconStatus = (
  status: WorkflowExecutionDetail["status"]
) => {
  if (status === "success") return "success";
  if (status === "failed") return "failure";
  if (status === "in_progress") return "pending";
  return "";
};

interface WorkflowResultsProps {
  workflowId: string;
  workflowExecutionId: string | null;
  initialWorkflowExecution?:
    | WorkflowExecutionDetail
    | WorkflowExecutionFailure
    | null;
  standalone?: boolean;
}

export function WorkflowExecutionResults({
  workflowId,
  workflowExecutionId,
  initialWorkflowExecution,
  standalone = false,
}: WorkflowResultsProps) {
  const api = useApi();
  const [refreshInterval, setRefreshInterval] = useState(1000);
  const [checks, setChecks] = useState(1);
  const [error, setError] = useState<string | null>(null);

  // TODO: enhance useWorkflowExecution hook with retry logic and use it here
  const { data: executionData, error: executionError } = useSWR(
    api.isReady() && workflowExecutionId
      ? `/workflows/${workflowId}/runs/${workflowExecutionId}`
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
      fallbackData: initialWorkflowExecution,
    }
  );

  // Get workflow definition
  const { data: workflowData, error: workflowError } = useSWR(
    api.isReady() ? `/workflows/${workflowId}` : null,
    (url) => api.get(url)
  );

  useEffect(() => {
    if (!standalone || !workflowData) {
      return;
    }
    const status = executionData?.error ? "failed" : executionData?.status;
    document.title = `${workflowData.name} - Workflow Results - Keep`;
    if (status) {
      setFavicon(convertWorkflowStatusToFaviconStatus(status));
    }
  }, [standalone, executionData, workflowData]);

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

  if (!executionData || !workflowData) {
    return <Loading />;
  }

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
    <WorkflowExecutionResultsInternal
      workflowId={workflowId}
      executionData={executionData}
      workflowRaw={workflowData.workflow_raw}
      checks={checks}
    />
  );
}

export function WorkflowExecutionResultsInternal({
  workflowId,
  executionData,
  workflowRaw,
  checks,
}: {
  executionData: WorkflowExecutionDetail | WorkflowExecutionFailure;
  workflowId: string | undefined;
  workflowRaw: string | undefined;
  checks: number;
}) {
  const [hoveredStep, setHoveredStep] = useState<string | null>(null);
  const [selectedStep, setSelectedStep] = useState<string | null>(null);

  let status: WorkflowExecutionDetail["status"] | undefined;
  let logs: WorkflowExecutionDetail["logs"] | undefined;
  let results: WorkflowExecutionDetail["results"] | undefined;
  let eventId: string | undefined;
  let eventType: string | undefined;

  if (isWorkflowExecution(executionData)) {
    status = executionData.status;
    logs = executionData.logs;
    results = executionData.results;
    eventId = executionData.event_id;
    eventType = executionData.event_type;
  }

  return (
    <div className="flex flex-col gap-4">
      {executionData.error && (
        <WorkflowExecutionError
          error={executionData.error}
          workflowId={workflowId}
          eventId={eventId}
          eventType={eventType}
        />
      )}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="flex flex-col gap-4">
          <Title>Workflow Logs</Title>
          <WorkflowExecutionLogs
            logs={logs ?? null}
            results={results ?? null}
            status={status ?? ""}
            checks={checks}
            hoveredStep={hoveredStep}
            selectedStep={selectedStep}
          />
        </div>
        <div className="flex flex-col gap-4">
          <Title>Workflow Definition</Title>
          <Card className="p-0 overflow-hidden">
            <WorkflowDefinitionYAML
              workflowRaw={workflowRaw ?? ""}
              executionLogs={logs}
              executionStatus={status}
              hoveredStep={hoveredStep}
              setHoveredStep={setHoveredStep}
              selectedStep={selectedStep}
              setSelectedStep={setSelectedStep}
            />
          </Card>
        </div>
      </div>
    </div>
  );
}
