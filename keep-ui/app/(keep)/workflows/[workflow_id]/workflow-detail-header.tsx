"use client";

import { useApi } from "@/shared/lib/hooks/useApi";
import { Workflow } from "@/shared/api/workflows";
import useSWR from "swr";
import Skeleton from "react-loading-skeleton";
import { Button, Switch, Text } from "@tremor/react";
import { useWorkflowRun } from "@/utils/hooks/useWorkflowRun";
import AlertTriggerModal from "../workflow-run-with-alert-modal";
import { CloudIcon, ExclamationTriangleIcon } from "@heroicons/react/20/solid";
import { Tooltip } from "@/shared/ui";
import Modal from "@/components/ui/Modal";
import { useCallback, useState } from "react";
import { EditWorkflowMetadataForm } from "@/features/edit-workflow-metadata";
import { useWorkflowStore } from "../builder/workflow-store";

function WorkflowSwitch() {
  const { v2Properties, updateV2Properties, saveWorkflow } = useWorkflowStore();
  return (
    <div className="flex items-center gap-2 px-2">
      <Switch
        color="orange"
        id="enabled"
        checked={v2Properties.disabled !== "true"}
        onChange={() => {
          updateV2Properties({
            ...v2Properties,
            disabled: v2Properties.disabled === "true" ? "false" : "true",
          });
          saveWorkflow();
        }}
      />
      <label htmlFor="enabled" className="font-medium">
        Enabled
      </label>
    </div>
  );
}

function WorkflowSyncStatus() {
  const { isPendingSync } = useWorkflowStore();
  return !isPendingSync ? (
    <Tooltip content="Saved to Keep">
      <CloudIcon className="w-4 h-4 text-gray-500" />
    </Tooltip>
  ) : (
    <Tooltip content="Not saved">
      <ExclamationTriangleIcon className="w-4 h-4 text-gray-500" />
    </Tooltip>
  );
}

function EditWorkflowMetadataModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const { workflowId, v2Properties, updateV2Properties, saveWorkflow } =
    useWorkflowStore();

  console.log("v2Properties", v2Properties);

  const updateWorkflowMetadata = useCallback(
    async (
      workflowId: string,
      { name, description }: { name: string; description: string }
    ) => {
      // Update properties first
      updateV2Properties({
        name,
        description,
      });
      saveWorkflow();

      onClose();
    },
    [saveWorkflow, updateV2Properties]
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      className="w-[600px]"
      title="Edit Workflow Metadata"
    >
      <EditWorkflowMetadataForm
        workflow={{
          id: workflowId,
          name: v2Properties.name,
          description: v2Properties.description,
        }}
        onCancel={onClose}
        onSubmit={({ name, description }) =>
          updateWorkflowMetadata(workflowId, { name, description })
        }
      />
    </Modal>
  );
}

export default function WorkflowDetailHeader({
  workflowId: workflow_id,
  initialData,
}: {
  workflowId: string;
  initialData?: Workflow;
}) {
  const api = useApi();
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const { data: workflow, error } = useSWR<Partial<Workflow>>(
    api.isReady() ? `/workflows/${workflow_id}` : null,
    (url: string) => api.get(url),
    { fallbackData: initialData, revalidateOnMount: false }
  );

  const { workflowId } = useWorkflowStore();

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
            <WorkflowSyncStatus />
          </h1>
          {workflow.description && (
            <Text className="line-clamp-5">
              <span data-testid="wf-description">{workflow.description}</span>
            </Text>
          )}
        </div>

        <div className="flex gap-2">
          <WorkflowSwitch />
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            onClick={() => setIsEditModalOpen(true)}
            disabled={!workflow || !workflowId}
          >
            Edit
          </Button>
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
      <EditWorkflowMetadataModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
      />
    </div>
  );
}
