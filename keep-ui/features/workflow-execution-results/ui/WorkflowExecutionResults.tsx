"use client";

import React, { useEffect, useState, useMemo } from "react";
import { Card, Callout, Button, Badge } from "@tremor/react";
import Loading from "@/app/(keep)/loading";
import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { TabGroup, Tab, TabList, TabPanel, TabPanels } from "@tremor/react";
import {
  WorkflowExecutionDetail,
  WorkflowExecutionFailure,
  isWorkflowExecution,
  isWorkflowFailure,
} from "@/shared/api/workflow-executions";
import { WorkflowExecutionError } from "./WorkflowExecutionError";
import { WorkflowExecutionLogs } from "./WorkflowExecutionLogs";
import { setFavicon } from "@/shared/ui/utils/favicon";
import { EmptyStateCard, ResizableColumns } from "@/shared/ui";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";
import { WorkflowYAMLEditorWithLogs } from "@/shared/ui/WorkflowYAMLEditorWithLogs";
import { useWorkflowExecutionDetail } from "@/entities/workflow-executions/model/useWorkflowExecutionDetail";
import { useWorkflowDetail } from "@/entities/workflows/model/useWorkflowDetail";
import { Workflow } from "@/shared/api/workflows";

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
  const [refreshInterval, setRefreshInterval] = useState(1000);
  const [checks, setChecks] = useState(0);

  const { data: executionData, error: executionError } =
    useWorkflowExecutionDetail(workflowId, workflowExecutionId, {
      onSuccess: (data) => {
        if (isWorkflowExecution(data)) {
          if (data.status === "in_progress") {
            setChecks((c) => c + 1);
          }
        }
      },
      dedupingInterval: 990,
      refreshInterval: refreshInterval,
      fallbackData: isWorkflowExecution(initialWorkflowExecution)
        ? initialWorkflowExecution
        : undefined,
    });

  const workflowRevision = isWorkflowExecution(executionData)
    ? executionData.workflow_revision
    : undefined;

  const { workflow: workflowData, error: workflowError } = useWorkflowDetail(
    !workflowYaml ? workflowId : null,
    workflowRevision ?? null
  );

  const finalYaml = workflowYaml ?? workflowData?.workflow_raw;

  useEffect(() => {
    if (!standalone || !executionData) {
      return;
    }
    const status = isWorkflowExecution(executionData)
      ? executionData.status
      : "failed";
    const workflowName =
      isWorkflowExecution(executionData) && executionData.workflow_name
        ? executionData.workflow_name
        : "Workflow";
    document.title = `${workflowName} - Workflow Results - Keep`;
    if (status) {
      setFavicon(convertWorkflowStatusToFaviconStatus(status));
    }
  }, [standalone, executionData]);

  useEffect(() => {
    if (!executionData) return;

    if (isWorkflowExecution(executionData)) {
      if (executionData.status !== "in_progress") {
        console.log("Stopping refresh interval");
        setRefreshInterval(0);
      }
    } else if (isWorkflowFailure(executionData)) {
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

  if (workflowError) {
    return (
      <Callout title="Error" icon={ExclamationCircleIcon} color="rose">
        Failed to load workflow definition
      </Callout>
    );
  }

  return (
    <WorkflowExecutionResultsInternal
      workflow={workflowData}
      executionData={executionData}
      workflowRaw={finalYaml}
      checks={checks}
      isLoading={refreshInterval > 0}
    />
  );
}

export function WorkflowExecutionResultsInternal({
  workflow,
  executionData,
  workflowRaw,
  checks,
  isLoading,
}: {
  executionData: WorkflowExecutionDetail | WorkflowExecutionFailure;
  workflow: Workflow;
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
      name: (
        <span className="flex items-center gap-2">
          Workflow Definition{" "}
          <Badge color="gray" size="xs">
            Revision {workflow.revision}
          </Badge>
        </span>
      ),
      content: (
        <div className="h-[calc(100vh-220px)]">
          <WorkflowYAMLEditorWithLogs
            workflowYamlString={workflowRaw ?? ""}
            workflowId={workflow.id}
            executionLogs={logs}
            executionStatus={status}
            hoveredStep={hoveredStep}
            setHoveredStep={setHoveredStep}
            selectedStep={selectedStep}
            setSelectedStep={setSelectedStep}
            readOnly={true}
            filename={workflow.id}
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
          workflowId={workflow.id}
          eventId={eventId}
          eventType={eventType}
        />
      )}
      <ResizableColumns initialLeftWidth={50}>
        <div className="pr-2">
          {logs && logs.length > 0 ? (
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
                  revalidateMultiple([`/workflows/${workflow.id}/runs`]);
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
