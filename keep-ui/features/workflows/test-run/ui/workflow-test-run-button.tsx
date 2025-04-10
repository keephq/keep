import { useMemo } from "react";
import type { DefinitionV2 } from "@/entities/workflows";
import { KeepLoader, showErrorToast } from "@/shared/ui";
import { useState } from "react";
import Modal from "@/components/ui/Modal";
import { getYamlWorkflowDefinition } from "@/entities/workflows/lib/parser";
import { extractWorkflowYamlDependencies } from "@/entities/workflows/lib/extractWorkflowYamlDependencies";
import { getBodyFromStringOrDefinitionOrObject } from "@/entities/workflows/lib/yaml-utils";
import { Button, ButtonProps, Callout, Title } from "@tremor/react";
import { ExclamationCircleIcon, PlayIcon } from "@heroicons/react/24/outline";
import { WorkflowExecutionResults } from "@/features/workflow-execution-results";
import { WorkflowAlertIncidentDependenciesForm } from "./workflow-alert-incident-dependencies-form";
import { useWorkflowTestRun } from "../model/useWorkflowTestRun";
import { v4 as uuidv4 } from "uuid";

interface WorkflowTestRunButtonProps {
  workflowId: string;
  definition: DefinitionV2 | null;
  isValid: boolean;
}

export function WorkflowTestRunButton({
  workflowId,
  definition,
  isValid,
  ...props
}: WorkflowTestRunButtonProps & ButtonProps) {
  const [isTestRunModalOpen, setIsTestRunModalOpen] = useState(false);
  const [workflowExecutionId, setWorkflowExecutionId] = useState<string | null>(
    null
  );
  const [error, setError] = useState<Error | null>(null);

  const yamlString = useMemo(() => {
    if (!definition?.value) {
      return null;
    }
    const workflow = getYamlWorkflowDefinition(definition.value);
    // NOTE: prevent the workflow from being disabled, so test run doesn't fail
    workflow.disabled = false;
    const body = getBodyFromStringOrDefinitionOrObject({
      workflow,
    });
    return body;
  }, [definition]);

  const dependencies = useMemo(() => {
    if (!yamlString) {
      return null;
    }
    return extractWorkflowYamlDependencies(yamlString);
  }, [yamlString]);

  const testRunWorkflow = useWorkflowTestRun();

  const closeWorkflowExecutionResultsModal = () => {
    setIsTestRunModalOpen(false);
    setWorkflowExecutionId(null);
    setError(null);
  };

  const handleCancel = (e: React.FormEvent) => {
    e.preventDefault();
    closeWorkflowExecutionResultsModal();
  };

  const handleTestRunWorkflow = async (
    eventType: "alert" | "incident",
    eventPayload: any
  ) => {
    if (!yamlString) {
      showErrorToast(new Error("Workflow is not initialized"));
      return;
    }
    try {
      const result = await testRunWorkflow(yamlString, eventType, eventPayload);
      if (!result) {
        setError(new Error("Failed to test run workflow"));
        return;
      }
      setWorkflowExecutionId(result.workflow_execution_id);
    } catch (error) {
      setError(
        error instanceof Error
          ? error
          : new Error(
              "An unknown error occurred during test run. Please try again."
            )
      );
    }
  };

  const handleClickTestRun = () => {
    if (!dependencies) {
      showErrorToast(new Error("Failed to parse workflow dependencies"));
      return;
    }
    setIsTestRunModalOpen(true);
    if (!dependencies.alert.length && !dependencies.incident.length) {
      handleTestRunWorkflow("alert", {
        id: "manual-run",
        name: "manual-run",
        lastReceived: new Date().toISOString(),
        source: ["manual"],
      });
      return;
    }
    // else will be handled in onSubmit of WorkflowAlertDependenciesForm
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

  const incidentStaticFields = [
    {
      key: "id",
      value: uuidv4(),
    },
    {
      key: "alerts_count",
      value: 1,
    },
    {
      key: "alert_sources",
      value: ["manual"],
    },
    {
      key: "services",
      value: ["manual"],
    },
    {
      key: "is_predicted",
      value: false,
    },
    {
      key: "is_candidate",
      value: false,
    },
  ];

  const renderModalContent = () => {
    if (error !== null) {
      return (
        <div className="flex justify-center">
          <Callout title="Error" icon={ExclamationCircleIcon} color="rose">
            {error.message}
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
            <div></div>
          </div>
          <div className="flex flex-col">
            <WorkflowExecutionResults
              workflowId={workflowId}
              workflowExecutionId={workflowExecutionId}
              workflowYaml={yamlString ?? ""}
            />
          </div>
        </div>
      );
    }
    if (dependencies) {
      if (dependencies.alert.length > 0 && dependencies.incident.length > 0) {
        return (
          <Callout title="Error" icon={ExclamationCircleIcon} color="rose">
            Alert and incident dependencies cannot be used together
          </Callout>
        );
      }
      if (dependencies.alert.length > 0) {
        return (
          <WorkflowAlertIncidentDependenciesForm
            type="alert"
            dependencies={dependencies.alert}
            staticFields={alertStaticFields}
            onCancel={closeWorkflowExecutionResultsModal}
            onSubmit={(payload) => handleTestRunWorkflow("alert", payload)}
            submitLabel="Test Run with Payload"
          />
        );
      }
      if (dependencies.incident.length > 0) {
        return (
          <WorkflowAlertIncidentDependenciesForm
            type="incident"
            dependencies={dependencies.incident}
            staticFields={incidentStaticFields}
            onCancel={closeWorkflowExecutionResultsModal}
            onSubmit={(payload) => handleTestRunWorkflow("incident", payload)}
            submitLabel="Test Run with Payload"
          />
        );
      }
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
        onClick={handleClickTestRun}
        {...props}
      >
        Test Run
      </Button>
      {isTestRunModalOpen && (
        <Modal
          isOpen={isTestRunModalOpen}
          onClose={closeWorkflowExecutionResultsModal}
          title="Test Run"
          description="Test run will use current definition (even unsaved changes), and will not be saved in execution history"
          className="max-w-7xl"
        >
          {renderModalContent()}
        </Modal>
      )}
    </>
  );
}
