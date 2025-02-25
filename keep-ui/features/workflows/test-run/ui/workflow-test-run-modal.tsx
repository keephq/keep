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

// It listens for the runRequestCount and triggers the test run of the workflow, opening the modal with the results.
export function WorkflowTestRunModal({ workflowId }: { workflowId: string }) {
  const { definition, runRequestCount } = useWorkflowStore();
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

  useEffect(() => {
    if (runRequestCount) {
      testRunWorkflow();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runRequestCount]);

  const testRunWorkflow = () => {
    if (!definition?.value) {
      showErrorToast(new Error("Workflow is not initialized"));
      return;
    }
    if (currentRequestId.current) {
      showErrorToast(new Error("Workflow is already running"));
      return;
    }
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
  );
}
