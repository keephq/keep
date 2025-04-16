"use client";

import React, { useEffect, useState, useMemo, useRef } from "react";
import { Card, Callout, Button, Badge } from "@tremor/react";
import Loading from "@/app/(keep)/loading";
import {
  ArrowPathIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/24/outline";
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
import { EmptyStateCard, MonacoEditor, ResizableColumns } from "@/shared/ui";
import { WorkflowYAMLEditorWithLogs } from "@/shared/ui/WorkflowYAMLEditorWithLogs";
import { useWorkflowExecutionDetail } from "@/entities/workflow-executions/model/useWorkflowExecutionDetail";
import { useWorkflowDetail } from "@/entities/workflows/model/useWorkflowDetail";
import { useWorkflowExecutionsRevalidation } from "@/entities/workflow-executions/model/useWorkflowExecutionsRevalidation";
import clsx from "clsx";

const WAIT_AFTER_STATUS_CHANGED = 2000;

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
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [refreshInterval, setRefreshInterval] = useState(1000);
  const [checks, setChecks] = useState(0);

  const {
    data: executionData,
    error: executionError,
    isValidating: isRevalidating,
  } = useWorkflowExecutionDetail(workflowId, workflowExecutionId, {
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

  const { workflow: latestWorkflowData } = useWorkflowDetail(workflowId, null);

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

  const stopRefreshInterval = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    // we wait a bit after the status changes to allow new logs to be loaded
    console.log("Stopping refresh interval in", WAIT_AFTER_STATUS_CHANGED);
    timeoutRef.current = setTimeout(() => {
      setRefreshInterval(0);
    }, WAIT_AFTER_STATUS_CHANGED);
  };

  useEffect(() => {
    if (!executionData) return;

    if (isWorkflowExecution(executionData)) {
      if (executionData.status !== "in_progress") {
        stopRefreshInterval();
      }
    } else if (isWorkflowFailure(executionData)) {
      stopRefreshInterval();
    }
  }, [executionData]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  if (!finalYaml && !workflowError && !executionError) {
    return <Loading />;
  }

  const isLatestRevision =
    isWorkflowExecution(executionData) &&
    executionData.workflow_revision === latestWorkflowData?.revision;

  return (
    <WorkflowExecutionResultsInternal
      workflowId={workflowId}
      workflowError={workflowError ?? null}
      executionError={executionError ?? null}
      executionData={executionData ?? null}
      workflowRaw={finalYaml}
      checks={checks}
      showRevision={workflowData !== undefined}
      isLoading={refreshInterval > 0}
      isRevalidating={isRevalidating}
      isLatestRevision={isLatestRevision}
    />
  );
}

const editorHeightClassName = "h-[calc(100vh-220px)]";

export function WorkflowExecutionResultsInternal({
  workflowId,
  workflowError,
  executionData,
  executionError,
  workflowRaw,
  isLatestRevision,
  showRevision,
  checks,
  isLoading,
  isRevalidating,
}: {
  workflowId: string;
  workflowError: Error | null;
  executionData: WorkflowExecutionDetail | WorkflowExecutionFailure | null;
  executionError: Error | null;
  isRevalidating: boolean;
  workflowRaw: string | undefined;
  checks: number;
  isLoading: boolean;
  isLatestRevision: boolean;
  showRevision: boolean;
}) {
  const [hoveredStep, setHoveredStep] = useState<string | null>(null);
  const [selectedStep, setSelectedStep] = useState<string | null>(null);

  let status: WorkflowExecutionDetail["status"] | undefined;
  let logs: WorkflowExecutionDetail["logs"] | undefined;
  let results: WorkflowExecutionDetail["results"] | undefined;
  let eventId: string | undefined;
  let eventType: string | undefined;
  const { revalidateForWorkflowExecution } =
    useWorkflowExecutionsRevalidation();

  if (isWorkflowExecution(executionData)) {
    status = executionData.status;
    logs = executionData.logs;
    results = executionData.results;
    eventId = executionData.event_id;
    eventType = executionData.event_type;
  }

  const executionId = isWorkflowExecution(executionData)
    ? executionData.id
    : null;

  const refreshExecutionData = () => {
    if (executionId) {
      revalidateForWorkflowExecution(workflowId, executionId);
    }
  };

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
      id: "workflow-definition",
      name: (
        <span className="flex items-center gap-2">
          Workflow Definition
          {!showRevision ? null : isLatestRevision ? (
            <Badge color="green" size="xs">
              Current
            </Badge>
          ) : (
            <Badge color="gray" size="xs">
              Rev.{" "}
              {isWorkflowExecution(executionData)
                ? executionData.workflow_revision
                : "unknown"}
            </Badge>
          )}
        </span>
      ),
      content: (
        <div className={editorHeightClassName}>
          {workflowRaw && !workflowError ? (
            <WorkflowYAMLEditorWithLogs
              value={workflowRaw}
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
          ) : (
            <Callout
              title="Error"
              icon={ExclamationCircleIcon}
              color="rose"
              className="mx-4"
            >
              Failed to load workflow definition for revision{" "}
              {isWorkflowExecution(executionData)
                ? executionData.workflow_revision
                : "unknown"}
            </Callout>
          )}
        </div>
      ),
    },
    ...(hasEvent
      ? [
          {
            id: "event-trigger",
            name: "Event Trigger",
            content:
              typeof eventData === "object" ? (
                <div className={editorHeightClassName}>
                  <MonacoEditor
                    value={JSON.stringify(eventData, null, 2)}
                    language="json"
                    theme="vs-light"
                    options={{
                      readOnly: true,
                      minimap: { enabled: false },
                      scrollBeyondLastLine: false,
                      fontSize: 12,
                      lineNumbers: "off",
                      folding: true,
                      wordWrap: "on",
                    }}
                  />
                </div>
              ) : (
                <pre className="whitespace-pre-wrap overflow-auto rounded-lg p-4 text-sm">
                  {eventData}
                </pre>
              ),
          },
        ]
      : []),
  ];

  const RefreshIcon = ({
    filter,
    className,
    ...props
  }: Omit<React.SVGProps<SVGSVGElement>, "ref">) => (
    <ArrowPathIcon
      className={clsx("w-4 h-4", className, isRevalidating && "animate-spin")}
      {...props}
    />
  );

  return (
    <div className="flex flex-col gap-4">
      <ResizableColumns initialLeftWidth={50}>
        <div className="pr-2">
          {executionError && (
            <Callout
              className="mb-4"
              title="Error"
              icon={ExclamationCircleIcon}
              color="rose"
            >
              Failed to load workflow execution
            </Callout>
          )}
          {isWorkflowFailure(executionData) && (
            <div className="mb-4">
              <WorkflowExecutionError
                error={executionData.error}
                workflowId={workflowId}
                eventId={eventId}
                eventType={eventType}
              />
            </div>
          )}
          {logs ? (
            <div className="flex flex-col gap-4 items-center">
              <Card className="p-0 overflow-hidden">
                <WorkflowExecutionLogs
                  logs={logs ?? null}
                  results={results ?? null}
                  status={status ?? ""}
                  checks={checks}
                  hoveredStep={hoveredStep}
                  selectedStep={selectedStep}
                  showSkeleton={!executionData || logs.length === 0}
                />
              </Card>
              {/* In case not all logs are loaded */}
              <Button
                variant="light"
                color="gray"
                size="sm"
                icon={RefreshIcon}
                onClick={refreshExecutionData}
              >
                Refresh
              </Button>
            </div>
          ) : (
            <EmptyStateCard title="No logs found">
              <Button
                variant="primary"
                color="orange"
                size="sm"
                icon={RefreshIcon}
                onClick={refreshExecutionData}
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
                  <Tab key={tab.id}>{tab.name}</Tab>
                ))}
              </TabList>
              <TabPanels>
                {tabs.map((tab) => (
                  <TabPanel key={tab.id}>{tab.content}</TabPanel>
                ))}
              </TabPanels>
            </TabGroup>
          </Card>
        </div>
      </ResizableColumns>
    </div>
  );
}
