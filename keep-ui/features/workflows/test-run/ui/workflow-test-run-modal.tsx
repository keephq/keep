import { useRef } from "react";
import { useWorkflowStore } from "@/entities/workflows";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepLoader, showErrorToast } from "@/shared/ui";
import { useState } from "react";
import { KeepApiError } from "@/shared/api/KeepApiError";
import { BuilderWorkflowTestRunModalContent } from "./builder-workflow-testrun-modal-content";
import Modal from "@/components/ui/Modal";
import { getYamlWorkflowDefinition } from "@/entities/workflows/lib/parser";
import { v4 as uuidv4 } from "uuid";
import { getBodyFromStringOrDefinitionOrObject } from "@/entities/workflows/lib/yaml-utils";
import { Button, Callout } from "@tremor/react";
import { PlayIcon } from "@heroicons/react/24/outline";

// It listens for the runRequestCount and triggers the test run of the workflow, opening the modal with the results.
export function WorkflowTestRunButton({ workflowId }: { workflowId: string }) {
  const { definition } = useWorkflowStore();
  const isValid = useWorkflowStore((state) => !!state.definition?.isValid);

  const api = useApi();
  const [testRunModalOpen, setTestRunModalOpen] = useState(false);
  const [workflowExecutionId, setWorkflowExecutionId] = useState<string | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);
  const currentRequestId = useRef<string | null>(null);
  const [workflowYamlSent, setWorkflowYamlSent] = useState<string | null>(null);

  const closeWorkflowExecutionResultsModal = () => {
    currentRequestId.current = null;
    setTestRunModalOpen(false);
    setWorkflowExecutionId(null);
    setError(null);
  };

  const testRunWorkflow = () => {
    if (!definition?.value) {
      showErrorToast(new Error("Workflow is not initialized"));
      return;
    }
    if (currentRequestId.current) {
      showErrorToast(new Error("Workflow is already running"));
      return;
    }
    // TODO: handle workflows with alert triggers, like in useWorkflowRun.ts
    const requestId = uuidv4();
    currentRequestId.current = requestId;
    setTestRunModalOpen(true);
    const workflow = getYamlWorkflowDefinition(definition.value);
    // NOTE: prevent the workflow from being disabled, so test run doesn't fail
    workflow.disabled = false;
    const body = getBodyFromStringOrDefinitionOrObject({
      workflow,
    });
    setWorkflowYamlSent(body);
    api
      .request(`/workflows/test`, {
        method: "POST",
        body,
        headers: { "Content-Type": "application/yaml" },
      })
      .then((data) => {
        if (currentRequestId.current !== requestId) {
          return;
        }
        setError(null);
        setWorkflowExecutionId(data.workflow_execution_id);
      })
      .catch((error) => {
        if (currentRequestId.current !== requestId) {
          return;
        }
        setError(
          error instanceof KeepApiError ? error.message : "Unknown error"
        );
        setWorkflowExecutionId(null);
      })
      .finally(() => {
        if (currentRequestId.current !== requestId) {
          return;
        }
        currentRequestId.current = null;
      });
  };

  return (
    <>
      <Button
        variant="primary"
        color="orange"
        size="md"
        className="min-w-28 disabled:opacity-70"
        icon={PlayIcon}
        disabled={!isValid}
        // TODO: check if it freezes UI
        onClick={testRunWorkflow}
      >
        Test Run
      </Button>
      <Modal
        isOpen={testRunModalOpen}
        onClose={closeWorkflowExecutionResultsModal}
        className="bg-gray-50 p-4 md:p-10 mx-auto max-w-7xl mt-20 border border-orange-600/50 rounded-md"
      >
        {workflowExecutionId !== null && (
          <BuilderWorkflowTestRunModalContent
            closeModal={closeWorkflowExecutionResultsModal}
            workflowExecutionId={workflowExecutionId}
            workflowId={workflowId ?? ""}
            workflowYamlSent={workflowYamlSent}
          />
        )}
        {error !== null && (
          <div className="flex justify-center">
            <Callout title="Workflow execution failed" color="red">
              {error}
            </Callout>
          </div>
        )}
        {workflowExecutionId === null && (
          <div className="flex justify-center">
            <KeepLoader loadingText="Waiting for workflow execution results..." />
          </div>
        )}
      </Modal>
    </>
  );
}
