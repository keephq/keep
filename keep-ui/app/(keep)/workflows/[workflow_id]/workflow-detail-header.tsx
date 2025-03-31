"use client";

import { useWorkflowDetail } from "@/entities/workflows/model/useWorkflowDetail";
import { Workflow } from "@/shared/api/workflows";
import { useWorkflowRun } from "@/utils/hooks/useWorkflowRun";
import { Button, Text } from "@tremor/react";
import Skeleton from "react-loading-skeleton";
import AlertTriggerModal from "../workflow-run-with-alert-modal";
import { ManualRunWorkflowModal } from "@/features/workflows/manual-run-workflow";

export default function WorkflowDetailHeader({
  workflowId: workflow_id,
  initialData,
}: {
  workflowId: string;
  initialData?: Workflow;
}) {
  const { workflow, isLoading, error } = useWorkflowDetail(
    workflow_id,
    initialData
  );

  const {
    isRunning,
    handleRunClick,
    getTriggerModalProps,
    getManualInputModalProps,
    isRunButtonDisabled,
    message,
    hasInputs,
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

      {/* Alert Trigger Modal */}
      {!!workflow && !!getTriggerModalProps && (
        <AlertTriggerModal {...getTriggerModalProps()} />
      )}

      {/* Manual Input Modal */}
      {!!workflow && !!getManualInputModalProps && (
        <ManualRunWorkflowModal
          workflow={workflow}
          handleClose={() => getManualInputModalProps().onClose()}
          isOpen={getManualInputModalProps().isOpen}
          onSubmit={getManualInputModalProps().onSubmit}
        />
      )}
    </div>
  );
}
