"use client";

import { useApi } from "@/shared/lib/hooks/useApi";
import { Workflow } from "@/shared/api/workflows";
import useSWR from "swr";
import Skeleton from "react-loading-skeleton";
import { Button, Switch, Text } from "@tremor/react";
import { useWorkflowRun } from "@/utils/hooks/useWorkflowRun";
import AlertTriggerModal from "../workflow-run-with-alert-modal";
import { useStore } from "../builder/builder-store";
import { CloudIcon, ExclamationTriangleIcon } from "@heroicons/react/20/solid";
import { Tooltip } from "@/shared/ui";
import Modal from "@/components/ui/Modal";
import { useCallback, useState } from "react";
import { EditWorkflowMetadataForm } from "@/features/edit-workflow-metadata";
import { useWorkflowBuilderContext } from "../builder/workflow-builder-context";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";

function WorkflowSwitch() {
  const { v2Properties, setV2Properties } = useStore();
  return (
    <div className="flex items-center gap-2 px-2">
      <Switch
        color="orange"
        id="enabled"
        checked={v2Properties.disabled !== "true"}
        onChange={() => {
          setV2Properties({
            ...v2Properties,
            disabled: v2Properties.disabled === "true" ? "false" : "true",
          });
        }}
      />
      <label htmlFor="enabled" className="font-medium">
        Enabled
      </label>
    </div>
  );
}

function WorkflowSyncStatus() {
  const { synced } = useStore();
  return synced ? (
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
  const { setDefinition, validatorConfigurationV2, triggerSave } =
    useWorkflowBuilderContext();
  const { v2Properties, nodes, edges, updateV2Properties } = useStore();
  const revalidateMultiple = useRevalidateMultiple();

  console.log("v2Properties", v2Properties);

  // TODO: move to builder store? or refactor to rely on the sync
  const updateWorkflowMetadata = useCallback(
    async (
      workflowId: string,
      { name, description }: { name: string; description: string }
    ) => {
      updateV2Properties({
        name,
        description,
      });
      // FIX: definition is not updated at the time of save
      // Wait for next tick to ensure definition is updated
      await new Promise((resolve) => setTimeout(resolve, 0));

      // Now trigger save
      await triggerSave();
      revalidateMultiple([`/workflows/${workflowId}`], { isExact: true });
      onClose();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [nodes, edges, v2Properties, validatorConfigurationV2]
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
          id: v2Properties.id,
          name: v2Properties.name,
          description: v2Properties.description,
        }}
        onCancel={onClose}
        onSubmit={({ name, description }) =>
          updateWorkflowMetadata(v2Properties.id, { name, description })
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

  const { v2Properties } = useStore();

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
            disabled={!workflow || !v2Properties.id}
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
