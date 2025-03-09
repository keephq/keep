import { useEffect, useRef } from "react";
import { useWorkflowStore } from "@/entities/workflows";
import {
  WorkflowExecutionFailure,
  WorkflowExecutionDetail,
} from "@/shared/api/workflow-executions";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { useState } from "react";
import { KeepApiError } from "@/shared/api/KeepApiError";
import { BuilderWorkflowTestRunModalContent } from "./builder-workflow-testrun-modal-content";
import Modal from "@/components/ui/Modal";
import { getYamlWorkflowDefinition } from "@/entities/workflows/lib/parser";
import { stringify } from "yaml";
import { v4 as uuidv4 } from "uuid";
import { Button } from "@/components/ui";
import { PlayIcon } from "@heroicons/react/20/solid";

// It listens for the runRequestCount and triggers the test run of the workflow, opening the modal with the results.
export function WorkflowTestRunButton({ workflowId }: { workflowId: string }) {
  const { definition } = useWorkflowStore();
  const isValid = useWorkflowStore((state) => !!state.definition?.isValid);

  const api = useApi();
  const [testRunModalOpen, setTestRunModalOpen] = useState(false);
  const [runningWorkflowExecution, setRunningWorkflowExecution] = useState<
    WorkflowExecutionDetail | WorkflowExecutionFailure | null
  >(null);
  const currentRequestId = useRef<string | null>(null);

  const closeWorkflowExecutionResultsModal = () => {
    currentRequestId.current = null;
    setTestRunModalOpen(false);
    setRunningWorkflowExecution(null);
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
    const body = stringify(workflow);
    api
      .request(`/workflows/test`, {
        method: "POST",
        body,
        headers: { "Content-Type": "application/yaml" },
      })
      .then((data) => {
        console.log("data", data, currentRequestId.current, requestId);
        if (currentRequestId.current !== requestId) {
          return;
        }
        setRunningWorkflowExecution({
          ...data,
        });
      })
      .catch((error) => {
        if (currentRequestId.current !== requestId) {
          return;
        }
        setRunningWorkflowExecution({
          error:
            error instanceof KeepApiError ? error.message : "Unknown error",
        });
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
        <BuilderWorkflowTestRunModalContent
          closeModal={closeWorkflowExecutionResultsModal}
          workflowExecution={runningWorkflowExecution}
          workflowId={workflowId ?? ""}
        />
      </Modal>
    </>
  );
}
