import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useProviders } from "../../../../utils/hooks/useProviders";
import { Workflow } from "@/shared/api/workflows";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { isProviderInstalled } from "@/shared/lib/provider-utils";
import { useWorkflowExecutionsRevalidation } from "@/entities/workflow-executions/model/useWorkflowExecutionsRevalidation";
import { parseWorkflowYamlToJSON } from "@/entities/workflows/lib/yaml-utils";
import { YamlWorkflowDefinitionSchema } from "@/entities/workflows/model/yaml.schema";
import {
  useUIBuilderUnsavedChanges,
  useWorkflowStore,
} from "@/entities/workflows/model/workflow-store";
import { useWorkflowYAMLEditorStore } from "@/entities/workflows/model/workflow-yaml-editor-store";
import { useWorkflowModals } from "@/features/workflows/manual-run-workflow";
import { extractWorkflowYamlDependencies } from "@/entities/workflows/lib/extractWorkflowYamlDependencies";
import { v4 as uuidv4 } from "uuid";
import {
  AlertWorkflowRunPayload,
  IncidentWorkflowRunPayload,
  WorkflowRunPayload,
} from "./types";

const noop = () => {};

// TODO: refactor this whole thing to be more intuitive and easier to test
export const useWorkflowRun = (workflow: Workflow) => {
  const api = useApi();
  const router = useRouter();
  const [isRunning, setIsRunning] = useState(false);
  const {
    openInputsModal,
    openAlertDependenciesModal,
    openIncidentDependenciesModal,
    openUnsavedChangesModal,
    closeUnsavedChangesModal,
    closeInputsModal,
    closeAlertDependenciesModal,
    closeIncidentDependenciesModal,
  } = useWorkflowModals();
  const { revalidateForWorkflow } = useWorkflowExecutionsRevalidation();
  const { data: providersData } = useProviders();
  const providers = providersData?.providers ?? [];
  const isUIBuilderUnsaved = useUIBuilderUnsavedChanges();
  const { hasUnsavedChanges: isYamlEditorUnsaved } =
    useWorkflowYAMLEditorStore();
  const { triggerSave: triggerSaveUIBuilder } = useWorkflowStore();
  const { requestSave: requestSaveYamlEditor } = useWorkflowYAMLEditorStore();
  let message = "";

  const parsedWorkflow = useMemo(() => {
    if (!workflow?.workflow_raw) {
      return null;
    }
    const parsed = parseWorkflowYamlToJSON(
      workflow.workflow_raw,
      YamlWorkflowDefinitionSchema
    );
    if (parsed.error) {
      console.error("Failed to parse workflow YAML", parsed.error);
    }
    return parsed;
  }, [workflow?.workflow_raw]);

  // Check if workflow has inputs defined
  const workflowInputs = useMemo(() => {
    return parsedWorkflow?.data?.workflow?.inputs || [];
  }, [parsedWorkflow]);

  const hasInputs = workflowInputs.length > 0;

  const dependencies = useMemo(() => {
    if (!workflow?.workflow_raw) {
      return null;
    }
    return extractWorkflowYamlDependencies(workflow?.workflow_raw);
  }, [workflow?.workflow_raw]);

  // TODO: extract static fields from CEL expressions too
  const alertStaticFields = useMemo(() => {
    const alertTrigger = parsedWorkflow?.data?.workflow?.triggers?.find(
      (trigger) => trigger.type === "alert"
    );
    if (!alertTrigger) {
      return [];
    }
    if (!alertTrigger?.filters || !alertTrigger?.filters.length) {
      return [];
    }
    return alertTrigger.filters;
  }, [parsedWorkflow]);

  const incidentStaticFields = useMemo(() => {
    const incidentTrigger = parsedWorkflow?.data?.workflow?.triggers?.find(
      (trigger) => trigger.type === "incident"
    );
    if (!incidentTrigger) {
      return [];
    }
    return [
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
  }, [parsedWorkflow]);

  const notInstalledProviders = useMemo(
    () =>
      workflow?.providers
        ?.filter(
          (workflowProvider) =>
            !isProviderInstalled(workflowProvider, providers)
        )
        .map((provider) => provider.type),
    [workflow?.providers, providers]
  );
  const uniqueNotInstalledProviders = [...new Set(notInstalledProviders)];
  const allProvidersInstalled = notInstalledProviders.length === 0;

  if (!workflow) {
    return {
      handleRunClick: noop,
      isRunning: false,
      isRunButtonDisabled: false,
      message: "",
      hasInputs: false,
    };
  }

  // Check if there is a manual trigger
  const hasManualTrigger = workflow?.triggers?.some(
    (trigger) => trigger.type === "manual"
  );

  const hasAlertTrigger = workflow?.triggers?.some(
    (trigger) => trigger.type === "alert"
  );

  const isWorkflowDisabled = !!workflow?.disabled;

  const getDisabledTooltip = () => {
    if (!allProvidersInstalled)
      return `Not all providers are installed: ${uniqueNotInstalledProviders.join(
        ", "
      )}`;
    if (!hasManualTrigger) return "No manual trigger available.";
    if (isWorkflowDisabled) {
      return "Workflow is Disabled";
    }
    return message;
  };

  const isRunButtonDisabled =
    isWorkflowDisabled ||
    !allProvidersInstalled ||
    (!hasManualTrigger && !hasAlertTrigger);

  if (isRunButtonDisabled) {
    message = getDisabledTooltip();
  }

  const runWorkflow = async (payload: WorkflowRunPayload) => {
    try {
      if (!workflow) {
        return;
      }
      setIsRunning(true);
      const result = await api.post(`/workflows/${workflow.id}/run`, payload);
      revalidateForWorkflow(workflow.id);

      const { workflow_execution_id } = result;
      router.push(`/workflows/${workflow.id}/runs/${workflow_execution_id}`);
    } catch (error) {
      showErrorToast(error, "Failed to start workflow");
    } finally {
      setIsRunning(false);
    }
  };

  /**
   * Orchestrates the workflow execution process by handling pre-run validations and data collection:
   * 1. Ensures all changes are saved to prevent data loss
   * 2. Collects required workflow inputs from user
   * 3. Gathers alert/incident context if workflow depends on them
   *
   * The function may trigger multiple modals in sequence before actually running the workflow,
   * with each modal's response feeding into subsequent calls until all required data is collected.
   */
  const handleRunClick = async ({
    skipUnsavedChangesModal = false,
    inputsValues = null,
    alertValues = null,
    incidentValues = null,
  }: {
    skipUnsavedChangesModal?: boolean;
    inputsValues?: Record<string, any> | null;
    alertValues?: AlertWorkflowRunPayload | null;
    incidentValues?: IncidentWorkflowRunPayload | null;
  } = {}) => {
    if (!workflow) {
      return;
    }

    // Prevent potential data loss by prompting to save changes before running
    if (
      (isUIBuilderUnsaved || isYamlEditorUnsaved) &&
      !skipUnsavedChangesModal
    ) {
      openUnsavedChangesModal({
        onSaveYaml: () => {
          requestSaveYamlEditor();
          // Re-run workflow once YAML changes are saved
          const unsubscribe = useWorkflowYAMLEditorStore.subscribe(
            (state, prevState) => {
              if (!state.hasUnsavedChanges && prevState.hasUnsavedChanges) {
                handleRunClick({ skipUnsavedChangesModal: true });
                closeUnsavedChangesModal();
                unsubscribe();
              }
            }
          );
        },
        onSaveUIBuilder: () => {
          triggerSaveUIBuilder();
          // Re-run workflow once UI Builder changes are saved
          const unsubscribe = useWorkflowStore.subscribe((state, prevState) => {
            if (state.changes === 0 && prevState.changes !== 0) {
              handleRunClick({ skipUnsavedChangesModal: true });
              closeUnsavedChangesModal();
              unsubscribe();
            }
          });
        },
        onRunWithoutSaving: () => {
          handleRunClick({ skipUnsavedChangesModal: true });
          closeUnsavedChangesModal();
        },
      });
      return;
    }

    // Collect required workflow inputs before execution
    if (hasInputs && !inputsValues) {
      openInputsModal({
        inputs: workflowInputs,
        onSubmit: (inputs) => {
          closeInputsModal();
          // Re-run with collected inputs to proceed with next validation step
          handleRunClick({ skipUnsavedChangesModal, inputsValues: inputs });
        },
      });
      return;
    }

    // If workflow needs alert context, collect it through modal
    if (dependencies && dependencies.alert.length > 0 && !alertValues) {
      openAlertDependenciesModal({
        workflow,
        staticFields: alertStaticFields,
        dependencies: dependencies.alert,
        onSubmit: (payload) => {
          closeAlertDependenciesModal();
          // Re-run with collected alert context to proceed with next validation step
          handleRunClick({
            skipUnsavedChangesModal,
            alertValues: payload,
            inputsValues,
          });
        },
      });
      return;
    }

    // If workflow needs incident context, collect it through modal
    if (dependencies && dependencies.incident.length > 0 && !incidentValues) {
      openIncidentDependenciesModal({
        workflow,
        dependencies: dependencies.incident,
        staticFields: incidentStaticFields,
        onSubmit: (payload) => {
          closeIncidentDependenciesModal();
          // Re-run with collected incident context to proceed with execution
          handleRunClick({
            skipUnsavedChangesModal,
            incidentValues: payload,
            inputsValues,
          });
        },
      });
      return;
    }

    // All required data collected, execute the workflow
    else {
      if (alertValues) {
        runWorkflow({
          ...alertValues,
          inputs: inputsValues ?? undefined,
        });
      } else if (incidentValues) {
        runWorkflow({
          ...incidentValues,
          inputs: inputsValues ?? undefined,
        });
      } else {
        runWorkflow({
          type: undefined,
          inputs: inputsValues ?? undefined,
        });
      }
    }
  };

  return {
    handleRunClick,
    isRunning,
    isRunButtonDisabled,
    message,
    hasInputs,
  };
};
