import { useMemo, useRef } from "react";
import type { DefinitionV2 } from "@/entities/workflows";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepLoader, showErrorToast } from "@/shared/ui";
import { useState } from "react";
import { KeepApiError } from "@/shared/api/KeepApiError";
import Modal from "@/components/ui/Modal";
import {
  extractWorkflowYamlDependencies,
  getYamlWorkflowDefinition,
  WorkflowYamlDependencies,
} from "@/entities/workflows/lib/parser";
import { v4 as uuidv4 } from "uuid";
import { getBodyFromStringOrDefinitionOrObject } from "@/entities/workflows/lib/yaml-utils";
import { Button, Callout, Title } from "@tremor/react";
import { PlayIcon } from "@heroicons/react/24/outline";
import { IoClose } from "react-icons/io5";
import { WorkflowExecutionResults } from "@/features/workflow-execution-results";
import { WorkflowAlertDependenciesForm } from "./workflow-alert-dependencies-form";
interface WorkflowTestRunButtonProps {
  workflowId: string;
  definition: DefinitionV2 | null;
  isValid: boolean;
}

export function WorkflowTestRunButton({
  workflowId,
  definition,
  isValid,
}: WorkflowTestRunButtonProps) {
  const api = useApi();
  const [testRunModalOpen, setTestRunModalOpen] = useState(false);
  const [workflowExecutionId, setWorkflowExecutionId] = useState<string | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);
  const currentRequestId = useRef<string | null>(null);
  const [workflowYamlSent, setWorkflowYamlSent] = useState<string | null>(null);
  const [dependencies, setDependencies] =
    useState<WorkflowYamlDependencies | null>(null);

  const closeWorkflowExecutionResultsModal = () => {
    currentRequestId.current = null;
    setTestRunModalOpen(false);
    setWorkflowExecutionId(null);
    setError(null);
  };

  const handleCancel = (e: React.FormEvent) => {
    e.preventDefault();
    closeWorkflowExecutionResultsModal();
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
    const dependencies = extractWorkflowYamlDependencies(body);
    setDependencies(dependencies);
    if (
      dependencies &&
      (dependencies.providers.length > 0 ||
        dependencies.secrets.length > 0 ||
        dependencies.inputs.length > 0 ||
        dependencies.alert.length > 0 ||
        dependencies.incident.length > 0)
    ) {
      return;
    }
    setWorkflowYamlSent(body);
    // TODO: extract dependencies from the workflow
    // TODO: move to useWorkflowActions
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

  const alertStaticFields = useMemo(() => {
    if (
      !definition?.value?.properties?.alert ||
      typeof definition?.value?.properties?.alert !== "object"
    ) {
      return [];
    }
    return Object.entries(definition?.value?.properties?.alert).map(
      ([key, value]) => ({
        key,
        value,
      })
    );
  }, [definition]);

  const renderModalContent = () => {
    if (dependencies) {
      if (dependencies.alert.length > 0 && dependencies.incident.length > 0) {
        return (
          <Callout title="Mixed alert and incident dependencies" color="red">
            Alert and incident dependencies cannot be used together
          </Callout>
        );
      }
      if (dependencies.alert.length > 0) {
        return (
          <WorkflowAlertDependenciesForm
            dependencies={dependencies.alert}
            staticFields={alertStaticFields}
            onCancel={closeWorkflowExecutionResultsModal}
            onSubmit={() => {}}
          />
        );
      }
    }
    if (error !== null) {
      return (
        <div className="flex justify-center">
          <Callout title="Workflow execution failed" color="red">
            {error}
          </Callout>
        </div>
      );
    }
    if (workflowExecutionId !== null) {
      return (
        <div className="flex flex-col gap-4">
          <div className="flex justify-between items-center">
            <div>
              <Title>Workflow Execution Results</Title>
            </div>
            <div>
              <button onClick={handleCancel}>
                <IoClose size={20} />
              </button>
            </div>
          </div>
          <div className="flex flex-col">
            <WorkflowExecutionResults
              workflowId={workflowId}
              workflowExecutionId={workflowExecutionId}
              workflowYaml={workflowYamlSent ?? ""}
            />
          </div>
        </div>
      );
    }
    return (
      <div className="flex justify-center">
        <KeepLoader loadingText="Waiting for workflow execution results..." />
      </div>
    );
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
        title="Test Run"
      >
        {renderModalContent()}
      </Modal>
    </>
  );
}
