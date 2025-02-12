import { useEffect, useMemo } from "react";
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
import { getWorkflowFromDefinition } from "@/entities/workflows/lib/parser";
import { stringify } from "yaml";

// It listens for the runRequestCount and triggers the test run of the workflow, opening the modal with the results.
export function WorkflowTestRunModal({ workflowId }: { workflowId: string }) {
  const { definition, runRequestCount } = useWorkflowStore();
  const api = useApi();
  const [testRunModalOpen, setTestRunModalOpen] = useState(false);
  const [runningWorkflowExecution, setRunningWorkflowExecution] = useState<
    WorkflowExecutionDetail | WorkflowExecutionFailure | null
  >(null);

  const closeWorkflowExecutionResultsModal = () => {
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
    setTestRunModalOpen(true);
    const body = stringify(getWorkflowFromDefinition(definition.value));
    api
      .request(`/workflows/test`, {
        method: "POST",
        body,
        headers: { "Content-Type": "text/html" },
      })
      .then((data) => {
        setRunningWorkflowExecution({
          ...data,
        });
      })
      .catch((error) => {
        setRunningWorkflowExecution({
          error:
            error instanceof KeepApiError ? error.message : "Unknown error",
        });
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
