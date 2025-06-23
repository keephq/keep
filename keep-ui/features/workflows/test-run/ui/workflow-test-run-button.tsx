import { useMemo } from "react";
import type { DefinitionV2 } from "@/entities/workflows";
import { KeepLoader, showErrorToast, Tooltip } from "@/shared/ui";
import { useState } from "react";
import Modal from "@/components/ui/Modal";
import { getYamlWorkflowDefinition } from "@/entities/workflows/lib/parser";
import { extractWorkflowYamlDependencies } from "@/entities/workflows/lib/extractWorkflowYamlDependencies";
import { getBodyFromStringOrDefinitionOrObject } from "@/entities/workflows/lib/yaml-utils";
import { Button, ButtonProps, Callout, Title } from "@tremor/react";
import { ExclamationCircleIcon, PlayIcon } from "@heroicons/react/24/outline";
import { WorkflowExecutionResults } from "@/features/workflow-execution-results";
import { WorkflowAlertIncidentDependenciesForm } from "@/entities/workflows/ui/WorkflowAlertIncidentDependenciesForm";
import { useWorkflowTestRun } from "../model/useWorkflowTestRun";
import { v4 as uuidv4 } from "uuid";
import { AlertWorkflowRunPayload } from "../../manual-run-workflow/model/types";
import { IncidentWorkflowRunPayload } from "../../manual-run-workflow/model/types";
import { WorkflowInputsForm } from "../../manual-run-workflow/ui/WorkflowInputsForm";

const manualEventPayload = {
  id: "manual-run",
  name: "manual-run",
  source: ["manual"],
};
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

  const [inputsValues, setInputsValues] = useState<Record<string, any> | null>(
    null
  );

  const yamlString = useMemo(() => {
    if (!definition?.value) {
      return null;
    }
    const workflow = getYamlWorkflowDefinition(definition.value);
    // NOTE: prevent the workflow from being disabled, so test run doesn't fail
    workflow.disabled = false;
    if (workflowId) {
      // if existing workflow, use it's real id for test run
      workflow.id = workflowId;
    }
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
    setInputsValues(null);
    setIsTestRunModalOpen(false);
    setWorkflowExecutionId(null);
    setError(null);
  };

  const handleTestRunWorkflow = async ({
    inputsValues = null,
    alertValues = null,
    incidentValues = null,
  }: {
    inputsValues?: Record<string, any> | null;
    alertValues?: AlertWorkflowRunPayload | null;
    incidentValues?: IncidentWorkflowRunPayload | null;
  }) => {
    if (!yamlString) {
      showErrorToast(new Error("Workflow is not initialized"));
      return;
    }
    try {
      let result;
      if (alertValues) {
        result = await testRunWorkflow(yamlString, {
          ...alertValues,
          inputs: inputsValues ?? undefined,
        });
      } else if (incidentValues) {
        result = await testRunWorkflow(yamlString, {
          ...incidentValues,
          inputs: inputsValues ?? undefined,
        });
      } else {
        result = await testRunWorkflow(yamlString, {
          type: "alert",
          body: {
            ...manualEventPayload,
            lastReceived: new Date().toISOString(),
          },
          inputs: inputsValues ?? undefined,
        });
      }
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

  const handleClickTestRun = () => {
    if (!dependencies) {
      showErrorToast(new Error("Failed to parse workflow dependencies"));
      return;
    }
    setIsTestRunModalOpen(true);
    if (
      !dependencies.inputs.length &&
      !dependencies.alert.length &&
      !dependencies.incident.length
    ) {
      handleTestRunWorkflow({});
      return;
    }
    // else will be handled in onSubmit of WorkflowAlertDependenciesForm
  };

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
        <div className="flex flex-col gap-4" data-testid="wf-test-run-results">
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
      if (dependencies.inputs.length > 0 && !inputsValues) {
        return (
          <WorkflowInputsForm
            workflowInputs={definition?.value?.properties?.inputs ?? []}
            onSubmit={(inputs) => {
              setInputsValues(inputs);
              if (!dependencies.alert.length && !dependencies.incident.length) {
                handleTestRunWorkflow({ inputsValues: inputs });
              }
            }}
            onCancel={closeWorkflowExecutionResultsModal}
          />
        );
      }
      if (dependencies.alert.length > 0) {
        return (
          <WorkflowAlertIncidentDependenciesForm
            type="alert"
            dependencies={dependencies.alert}
            staticFields={alertStaticFields}
            onCancel={closeWorkflowExecutionResultsModal}
            onSubmit={({ type, body }) =>
              handleTestRunWorkflow({
                alertValues: { type, body },
                inputsValues,
              })
            }
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
            onSubmit={({ type, body }) =>
              handleTestRunWorkflow({
                incidentValues: { type, body },
                inputsValues,
              })
            }
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

  const testRunDescription = useMemo(() => {
    if (!isValid) {
      return "Workflow is not valid";
    }
    return `Test run with current changes${
      dependencies ? " and provided payload" : ""
    }. Will not be saved in history`;
  }, [isValid, dependencies]);

  return (
    <>
      <Tooltip content={testRunDescription}>
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
      </Tooltip>
      {isTestRunModalOpen && (
        <Modal
          isOpen={isTestRunModalOpen}
          onClose={closeWorkflowExecutionResultsModal}
          title="Test Run"
          description={testRunDescription}
          className="max-w-7xl"
        >
          {renderModalContent()}
        </Modal>
      )}
    </>
  );
}
