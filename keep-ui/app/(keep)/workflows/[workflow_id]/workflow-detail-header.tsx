"use client";

import { useApi } from "@/shared/lib/hooks/useApi";
import { Workflow } from "@/shared/api/workflows";
import useSWR from "swr";
import Skeleton from "react-loading-skeleton";
import { Button, Text } from "@tremor/react";
import { useWorkflowRun } from "@/utils/hooks/useWorkflowRun";
import AlertTriggerModal from "../workflow-run-with-alert-modal";

export default function WorkflowDetailHeader({
  workflowId: workflow_id,
  initialData,
}: {
  workflowId: string;
  initialData?: Workflow;
}) {
  const api = useApi();
  const {
    data: workflow,
    isLoading,
    error,
  } = useSWR<Partial<Workflow>>(
    api.isReady() ? `/workflows/${workflow_id}` : null,
    (url: string) => api.get(url),
    { fallbackData: initialData }
  );

  const {
    isRunning,
    handleRunClick,
    getTriggerModalProps,
    isRunButtonDisabled,
    message,
  } = useWorkflowRun(workflow as Workflow);

  if (error) {
    return <div>Error loading workflow</div>;
  }

  if (isLoading || !workflow) {
    return (
      <div>
        <h1 className="text-2xl line-clamp-2 font-extrabold">
          <Skeleton className="w-1/2 h-4" />
        </h1>
        <Skeleton className="w-3/4 h-4" />
        <Skeleton className="w-1/2 h-4" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-end text-sm gap-2">
        <div>
          <h1 className="text-2xl line-clamp-2 font-bold">{workflow.name}</h1>
          {workflow.description && (
            <Text className="line-clamp-5">
              <span>{workflow.description}</span>
            </Text>
          )}
        </div>
        {!!workflow && (
          <Button
            color="orange"
            disabled={isRunning || isRunButtonDisabled}
            className="p-2 px-4"
            onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
              e.stopPropagation();
              e.preventDefault();
              handleRunClick?.();
            }}
            tooltip={message}
          >
            {isRunning ? "Running..." : "Run now"}
          </Button>
        )}
      </div>

      {!!workflow && !!getTriggerModalProps && (
        <AlertTriggerModal {...getTriggerModalProps()} />
      )}
    </div>
  );
}
