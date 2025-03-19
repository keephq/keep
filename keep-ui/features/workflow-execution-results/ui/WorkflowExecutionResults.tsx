"use client";

import React, { useEffect, useState, useMemo } from "react";
import { Card, Callout, Button } from "@tremor/react";
import Loading from "@/app/(keep)/loading";
import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { TabGroup, Tab, TabList, TabPanel, TabPanels } from "@tremor/react";
import useSWR, { useSWRConfig } from "swr";
import {
  WorkflowExecutionDetail,
  WorkflowExecutionFailure,
  isWorkflowExecution,
} from "@/shared/api/workflow-executions";
import { useApi } from "@/shared/lib/hooks/useApi";
import MonacoYAMLEditor from "@/shared/ui/YAMLCodeblock/ui/MonacoYAMLEditor";
import { WorkflowExecutionError } from "./WorkflowExecutionError";
import { WorkflowExecutionLogs } from "./WorkflowExecutionLogs";
import { setFavicon } from "@/shared/ui/utils/favicon";
import { EmptyStateCard, JsonCard, ResizableColumns } from "@/shared/ui";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";

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
  workflowYaml?: string;
}

export function WorkflowExecutionResults({
  workflowId,
  workflowExecutionId,
  initialWorkflowExecution,
  standalone = false,
  workflowYaml,
}: WorkflowResultsProps) {
  const api = useApi();
  const [refreshInterval, setRefreshInterval] = useState(1000);
  const [checks, setChecks] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const {
    data: executionData,
    error: executionError,
    isValidating,
    isLoading,
  } = useSWR(
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
      dedupingInterval: 990,
      refreshInterval: refreshInterval,
      fallbackData: initialWorkflowExecution,
    }
  );

  const { data: workflowData, error: workflowError } = useSWR(
    api.isReady() && !workflowYaml ? `/workflows/${workflowId}` : null,
    (url) => api.get(url)
  );

  const finalYaml = workflowYaml ?? workflowData?.workflow_raw;

  useEffect(() => {
    if (!standalone || !executionData) {
      return;
    }
    const status = executionData.error ? "failed" : executionData.status;
    document.title = `${executionData.workflow_name} - Workflow Results - Keep`;
    if (status) {
      setFavicon(convertWorkflowStatusToFaviconStatus(status));
    }
  }, [standalone, executionData]);

  useEffect(() => {
    if (!executionData) return;

    if (executionData?.status !== "in_progress") {
      console.log("Stopping refresh interval");
      setRefreshInterval(0);
    }
    if (executionData.error) {
      setError(executionData?.error);
      setRefreshInterval(0);
    } else if (executionData?.status === "success") {
      setError(executionData?.error);
      setRefreshInterval(0);
    }
  }, [executionData]);

  if (!executionData || !finalYaml) {
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

  if (error) {
    return (
      <Callout title="Error" icon={ExclamationCircleIcon} color="rose">
        {error}
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
    <>
      <WorkflowExecutionResultsInternal
        workflowId={workflowId}
        executionData={executionData}
        workflowRaw={finalYaml}
        checks={checks}
        isLoading={refreshInterval > 0}
      />
    </>
  );
}

export function WorkflowExecutionResultsInternal({
  workflowId,
  executionData,
  workflowRaw,
  checks,
  isLoading,
}: {
  executionData: WorkflowExecutionDetail | WorkflowExecutionFailure;
  workflowId: string;
  workflowRaw: string | undefined;
  checks: number;
  isLoading: boolean;
}) {
  const [hoveredStep, setHoveredStep] = useState<string | null>(null);
  const [selectedStep, setSelectedStep] = useState<string | null>(null);

  let status: WorkflowExecutionDetail["status"] | undefined;
  let logs: WorkflowExecutionDetail["logs"] | undefined;
  let results: WorkflowExecutionDetail["results"] | undefined;
  let eventId: string | undefined;
  let eventType: string | undefined;
  const revalidateMultiple = useRevalidateMultiple();
  if (isWorkflowExecution(executionData)) {
    status = executionData.status;
    logs = executionData.logs;
    results = executionData.results;
    eventId = executionData.event_id;
    eventType = executionData.event_type;
  }

  const hasEvent = useMemo(() => {
    if (!logs) {
      return false;
    }
    return logs.some((log) => log.context?.event);
  }, [logs]);

  const eventData = useMemo(() => {
    if (!logs) return null;
    const eventLog = logs.find((log) => log.context?.event);
    if (!eventLog?.context?.event) return null;

    if (typeof eventLog.context.event === "string") {
      try {
        return JSON.parse(eventLog.context.event);
      } catch (e) {
        return eventLog.context.event;
      }
    }
    return eventLog.context.event;
  }, [logs]);

  const tabs = [
    {
      name: "Workflow Definition",
      content: (
        <div className="h-[calc(100vh-220px)]">
          <MonacoYAMLEditor
            workflowRaw={workflowRaw ?? ""}
            workflowId={workflowId}
            executionLogs={logs}
            executionStatus={status}
            hoveredStep={hoveredStep}
            setHoveredStep={setHoveredStep}
            selectedStep={selectedStep}
            setSelectedStep={setSelectedStep}
            readOnly={true}
            filename={workflowId}
          />
        </div>
      ),
    },
    ...(hasEvent
      ? [
          {
            name: "Event Trigger",
            content: (
              <div className="p-4">
                <pre className="whitespace-pre-wrap overflow-auto rounded-lg p-4 text-sm">
                  {typeof eventData === "object"
                    ? JSON.stringify(eventData, null, 2)
                    : eventData}
                </pre>
              </div>
            ),
          },
        ]
      : []),
  ];

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
      <ResizableColumns initialLeftWidth={50}>
        <div className="pr-2">
          {logs ? (
            <Card className="p-0 overflow-hidden">
              <WorkflowExecutionLogs
                logs={logs ?? null}
                results={results ?? null}
                status={status ?? ""}
                checks={checks}
                hoveredStep={hoveredStep}
                selectedStep={selectedStep}
                isLoading={isLoading}
              />
            </Card>
          ) : (
            <EmptyStateCard
              title="No logs found"
              description="The workflow is still running"
            >
              <Button
                variant="primary"
                color="orange"
                size="sm"
                onClick={() => {
                  revalidateMultiple([`/workflows/${workflowId}/runs`]);
                }}
              >
                Refresh
              </Button>
            </EmptyStateCard>
          )}
        </div>
        <div className="px-2">
          <Card className="p-0 overflow-hidden">
            <TabGroup>
              <TabList className="p-2">
                {tabs.map((tab) => (
                  <Tab key={tab.name}>{tab.name}</Tab>
                ))}
              </TabList>
              <TabPanels>
                {tabs.map((tab) => (
                  <TabPanel key={tab.name}>{tab.content}</TabPanel>
                ))}
              </TabPanels>
            </TabGroup>
          </Card>
        </div>
      </ResizableColumns>
    </div>
  );
}
