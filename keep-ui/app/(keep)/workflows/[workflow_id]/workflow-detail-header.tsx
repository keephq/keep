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
    { fallbackData: initialData, revalidateOnMount: false }
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

  if (!workflow) {
    return (
      <div className="flex flex-col gap-2">
        <div className="!w-1/2 h-8">
          <Skeleton className="w-full h-full" />
        </div>
        <div className="!w-3/4 h-4">
          <Skeleton className="w-full h-full" />
        </div>
        <div className="!w-2/5 h-4">
          <Skeleton className="w-full h-full" />
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-end text-sm gap-2">
        <div>
          <h1
            className="text-2xl line-clamp-2 font-bold flex items-baseline gap-2"
            data-testid="wf-name"
          >
            {workflow.name}
          </h1>
          {workflow.description && (
            <Text className="line-clamp-5">
              <span data-testid="wf-description">{workflow.description}</span>
            </Text>
          )}
        </div>

        <div className="flex gap-2">
          {!!workflow && (
            <Button
              size="xs"
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
      </div>

      {!!workflow && !!getTriggerModalProps && (
        <AlertTriggerModal {...getTriggerModalProps()} />
      )}
    </div>
  );
}
