import { useState, useMemo, useCallback } from "react";
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
  useWorkflowEditorChangesSaved,
  useWorkflowStore,
} from "@/entities/workflows/model/workflow-store";
import { useWorkflowYAMLEditorStore } from "@/entities/workflows/model/workflow-yaml-editor-store";
import { useWorkflowModals } from "@/features/workflows/manual-run-workflow";
import { extractWorkflowYamlDependencies } from "@/entities/workflows/lib/extractWorkflowYamlDependencies";
import { v4 as uuidv4 } from "uuid";

const noop = () => {};

// TODO: refactor this whole thing to be more intuitive and easier to test
export const useWorkflowRun = (workflow: Workflow) => {
  const api = useApi();
  const router = useRouter();
  const [isRunning, setIsRunning] = useState(false);
  const {
    openManualInputModal,
    openAlertDependenciesModal,
    openIncidentDependenciesModal,
    openUnsavedChangesModal,
  } = useWorkflowModals();
  const { revalidateForWorkflow } = useWorkflowExecutionsRevalidation();
  const { data: providersData } = useProviders();
  const providers = providersData?.providers ?? [];
  const { isInitialized: isWorkflowEditorInitialized } = useWorkflowStore();
  const isCurrentWorkflowChangesSaved = useWorkflowEditorChangesSaved();
  const { hasUnsavedChanges: hasYamlEditorUnsavedChanges } =
    useWorkflowYAMLEditorStore();
  const { triggerSave } = useWorkflowStore();
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

  const runWorkflow = async (payload: object) => {
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

  const handleRunClick = useCallback(
    async ({
      skipUnsavedChangesModal = false,
    }: {
      skipUnsavedChangesModal?: boolean;
    } = {}) => {
      if (!workflow) {
        return;
      }

      if (
        ((isWorkflowEditorInitialized && !isCurrentWorkflowChangesSaved) ||
          hasYamlEditorUnsavedChanges) &&
        !skipUnsavedChangesModal
      ) {
        openUnsavedChangesModal({
          onSaveYaml: () => {
            // TODO: implement
          },
          onSaveUIBuilder: () => {
            triggerSave();
            setTimeout(() => {
              handleRunClick();
            }, 1000);
          },
          onRunWithoutSaving: () => {
            handleRunClick({ skipUnsavedChangesModal: true });
          },
        });
        return;
      }

      // First, check if workflow has inputs
      if (hasInputs) {
        openManualInputModal({
          workflow,
          onSubmit: runWorkflow,
        });
        return;
      }

      // if it has dependencies, open the alert modal
      if (dependencies && dependencies.alert.length > 0) {
        openAlertDependenciesModal({
          workflow,
          staticFields: alertStaticFields,
          dependencies: dependencies.alert,
          onSubmit: runWorkflow,
        });
        return;
      }

      if (dependencies && dependencies.incident.length > 0) {
        openIncidentDependenciesModal({
          workflow,
          dependencies: dependencies.incident,
          staticFields: incidentStaticFields,
          onSubmit: runWorkflow,
        });
        return;
      }

      // else, no dependencies or inputs, just run it
      else {
        runWorkflow({});
      }
    },
    [
      workflow,
      isWorkflowEditorInitialized,
      isCurrentWorkflowChangesSaved,
      hasYamlEditorUnsavedChanges,
      dependencies,
      alertStaticFields,
      incidentStaticFields,
      hasInputs,
    ]
  );

  return {
    handleRunClick,
    isRunning,
    isRunButtonDisabled,
    message,
    hasInputs,
  };
};
