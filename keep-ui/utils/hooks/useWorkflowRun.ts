import { useState } from "react";
import { useSession } from "next-auth/react";
import { useApiUrl } from "./useConfig";
import { useRouter } from "next/navigation";
import { useProviders } from "./useProviders";
import { Filter, Workflow } from "app/workflows/models";
import { Provider } from "app/providers/providers";

interface ProvidersData {
  providers: { [key: string]: { providers: Provider[] } };
}

export const useWorkflowRun = (workflow: Workflow) => {
  const router = useRouter();
  const [isRunning, setIsRunning] = useState(false);
  const { data: session, status, update } = useSession();
  const accessToken = session?.accessToken;
  const [isAlertTriggerModalOpen, setIsAlertTriggerModalOpen] = useState(false);
  let message = "";
  const [alertFilters, setAlertFilters] = useState<Filter[]>([]);
  const [alertDependencies, setAlertDependencies] = useState<string[]>([]);
  const apiUrl = useApiUrl();

  const { data: providersData = { providers: {} } as ProvidersData } =
    useProviders();
  const providers = providersData.providers;

  if (!workflow) {
    return {};
  }

  const notInstalledProviders = workflow?.providers
    ?.filter(
      (workflowProvider) =>
        !workflowProvider.installed &&
        Object.values(providers || {}).some(
          (provider) =>
            provider.type === workflowProvider.type &&
            provider.config &&
            Object.keys(provider.config).length > 0
        )
    )
    .map((provider) => provider.type);

  const allProvidersInstalled = notInstalledProviders.length === 0;

  // Check if there is a manual trigger
  const hasManualTrigger = workflow?.triggers?.some(
    (trigger) => trigger.type === "manual"
  ); // Replace 'manual' with the actual value that represents a manual trigger in your data

  const hasAlertTrigger = workflow?.triggers?.some(
    (trigger) => trigger.type === "alert"
  );

  const isWorkflowDisabled = !!workflow?.disabled;

  const getDisabledTooltip = () => {
    if (!allProvidersInstalled)
      return `Not all providers are installed: ${notInstalledProviders.join(
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
      const response = await fetch(`${apiUrl}/workflows/${workflow?.id}/run`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        // Workflow started successfully
        const responseData = await response.json();
        const { workflow_execution_id } = responseData;
        router.push(`/workflows/${workflow?.id}/runs/${workflow_execution_id}`);
      } else {
        console.error("Failed to start workflow");
      }
    } catch (error) {
      console.error("An error occurred while starting workflow", error);
    } finally {
      setIsRunning(false);
    }
    setIsRunning(false);
  };

  const handleRunClick = async () => {
    if (!workflow) {
      return;
    }
    const dependencies = extractAlertDependencies(workflow?.workflow_raw);
    const hasDependencies = dependencies.length > 0;

    // if it has dependencies, open the modal
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
    // else, no dependencies, just run it
    else {
      runWorkflow({});
    }
  };

  const handleAlertTriggerModalSubmit = (payload: any) => {
    runWorkflow(payload); // Function to run the workflow with the payload
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

  return {
    handleRunClick,
    isRunning,
    getTriggerModalProps,
    isRunButtonDisabled,
    message,
  };
};
