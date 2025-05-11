import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useProviders } from "./useProviders";
import { Filter, Workflow } from "@/shared/api/workflows";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { isProviderInstalled } from "@/shared/lib/provider-utils";
import { useWorkflowExecutionsRevalidation } from "@/entities/workflow-executions/model/useWorkflowExecutionsRevalidation";
import { parseWorkflowYamlStringToJSON } from "@/entities/workflows/lib/yaml-utils";
import type { WorkflowInput } from "@/entities/workflows/model/yaml.schema";

const noop = () => {};

// TODO: refactor this whole thing to be more intuitive and easier to test
export const useWorkflowRun = (workflow: Workflow) => {
  const api = useApi();
  const router = useRouter();
  const [isRunning, setIsRunning] = useState(false);
  const [isAlertTriggerModalOpen, setIsAlertTriggerModalOpen] = useState(false);
  const [isManualInputModalOpen, setIsManualInputModalOpen] = useState(false);
  let message = "";
  const [alertFilters, setAlertFilters] = useState<Filter[]>([]);
  const [alertDependencies, setAlertDependencies] = useState<string[]>([]);
  const [workflowInputs, setWorkflowInputs] = useState<WorkflowInput[]>([]);
  const { revalidateForWorkflow } = useWorkflowExecutionsRevalidation();
  const { data: providersData } = useProviders();
  const providers = providersData?.providers ?? [];

  // Check if workflow has inputs defined
  useEffect(() => {
    if (workflow?.workflow_raw) {
      try {
        const parsedWorkflow = parseWorkflowYamlStringToJSON(
          workflow.workflow_raw
        );
        const inputs = parsedWorkflow?.workflow?.inputs || [];
        setWorkflowInputs(inputs);
      } catch (error) {
        console.error("Failed to parse workflow YAML:", error);
        setWorkflowInputs([]);
      }
    } else {
      setWorkflowInputs([]);
    }
  }, [workflow]);

  if (!workflow) {
    return {
      handleRunClick: noop,
      isRunning: false,
      getTriggerModalProps: null,
      getManualInputModalProps: null,
      isRunButtonDisabled: false,
      message: "",
      hasInputs: false,
    };
  }

  const notInstalledProviders = workflow?.providers
    ?.filter(
      (workflowProvider) => !isProviderInstalled(workflowProvider, providers)
    )
    .map((provider) => provider.type);
  const uniqueNotInstalledProviders = [...new Set(notInstalledProviders)];

  const allProvidersInstalled = notInstalledProviders.length === 0;

  // Check if there is a manual trigger
  const hasManualTrigger = workflow?.triggers?.some(
    (trigger) => trigger.type === "manual"
  );

  const hasAlertTrigger = workflow?.triggers?.some(
    (trigger) => trigger.type === "alert"
  );

  const hasInputs = workflowInputs.length > 0;

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
  function extractAlertDependencies(workflowRaw: string): string[] {
    const dependencyRegex = /(?<!if:.*?)(\{\{\s*alert\.[\w.]+\s*\}\})/g;
    const dependencies = workflowRaw.match(dependencyRegex);

    if (!dependencies) {
      return [];
    }

    // Use a Set to handle duplicates
    const uniqueDependencies = new Set<string>();

    dependencies.forEach((dep) => {
      const match = dep.match(/alert\.([\w.]+)/);
      if (match) {
        uniqueDependencies.add(match[1]);
      }
    });

    // Convert Set to Array
    return Array.from(uniqueDependencies);
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

  const handleRunClick = async () => {
    if (!workflow) {
      return;
    }

    // First, check if workflow has inputs
    if (hasInputs) {
      setIsManualInputModalOpen(true);
      return;
    }

    // If no inputs, check for alert dependencies
    const dependencies = extractAlertDependencies(workflow?.workflow_raw);
    const hasDependencies = dependencies.length > 0;

    // if it has dependencies, open the alert modal
    if (hasDependencies) {
      setAlertDependencies(dependencies);
      // extract the filters
      // TODO: support more than one trigger
      for (const trigger of workflow?.triggers || []) {
        if (trigger.type === "alert") {
          const staticAlertFilters = trigger.filters || [];
          setAlertFilters(staticAlertFilters);
          break;
        }
      }
      setIsAlertTriggerModalOpen(true);
      return;
    }
    // else, no dependencies or inputs, just run it
    else {
      runWorkflow({});
    }
  };

  const handleAlertTriggerModalSubmit = (payload: any) => {
    runWorkflow(payload); // Function to run the workflow with the payload
  };

  const handleManualInputModalSubmit = (inputs: Record<string, any>) => {
    runWorkflow({ inputs }); // Function to run the workflow with the input values
  };

  const getTriggerModalProps = () => {
    return {
      isOpen: isAlertTriggerModalOpen,
      onClose: () => setIsAlertTriggerModalOpen(false),
      onSubmit: handleAlertTriggerModalSubmit,
      staticFields: alertFilters,
      dependencies: alertDependencies,
    };
  };

  const getManualInputModalProps = () => {
    return {
      isOpen: isManualInputModalOpen,
      onClose: () => setIsManualInputModalOpen(false),
      onSubmit: handleManualInputModalSubmit,
      workflow: workflow,
    };
  };

  return {
    handleRunClick,
    isRunning,
    getTriggerModalProps,
    getManualInputModalProps,
    isRunButtonDisabled,
    message,
    hasInputs,
  };
};
