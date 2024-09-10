import { useState } from "react";
import { useSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import { useRouter } from "next/navigation";
import { Filter, Workflow } from "app/workflows/models";

export const useWorkflowRun = (workflow: Workflow) => {

    const router = useRouter();
    const [isRunning, setIsRunning] = useState(false);
    const { data: session, status, update } = useSession();
    const accessToken = session?.accessToken;
    const [isAlertTriggerModalOpen, setIsAlertTriggerModalOpen] = useState(false);
    let message = ""
    const [alertFilters, setAlertFilters] = useState<Filter[]>([]);
    const [alertDependencies, setAlertDependencies] = useState<string[]>([]);

    const apiUrl = getApiURL();

    if (!workflow) {
        return {};
    }
    const allProvidersInstalled = workflow?.providers?.every(
        (provider) => provider.installed
    );

    // Check if there is a manual trigger
    const hasManualTrigger = workflow?.triggers?.some(
        (trigger) => trigger.type === "manual"
    ); // Replace 'manual' with the actual value that represents a manual trigger in your data

    const hasAlertTrigger = workflow?.triggers?.some(
        (trigger) => trigger.type === "alert"
    );

    const getDisabledTooltip = () => {
        if (!allProvidersInstalled) return "Not all providers are installed.";
        if (!hasManualTrigger) return "No manual trigger available.";
        return message;
    };

    const isRunButtonDisabled = !allProvidersInstalled || (!hasManualTrigger && !hasAlertTrigger);

    if (isRunButtonDisabled) {
        message = getDisabledTooltip();
    }
    function extractAlertDependencies(workflowRaw: string): string[] {
        const dependencyRegex = /(?<!if:.*?)(\{\{\s*alert\.[\w.]+\s*\}\})/g;
        const dependencies = workflowRaw.match(dependencyRegex);

        if (!dependencies) {
            return [];
        }

        // Convert Set to Array
        const uniqueDependencies = Array.from(new Set(dependencies)).reduce<
            string[]
        >((acc, dep) => {
            // Ensure 'dep' is treated as a string
            const match = dep.match(/alert\.([\w.]+)/);
            if (match) {
                acc.push(match[1]);
            }
            return acc;
        }, []);

        return uniqueDependencies;
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
        const hasAlertTrigger = workflow?.triggers?.some(
            (trigger) => trigger.type === "alert"
        );

        // if it needs alert payload, than open the modal
        if (hasAlertTrigger) {
            // extract the filters
            // TODO: support more than one trigger
            for (const trigger of workflow?.triggers) {
                // at least one trigger is alert, o/w hasAlertTrigger was false
                if (trigger.type === "alert") {
                    const staticAlertFilters = trigger.filters || [];
                    setAlertFilters(staticAlertFilters);
                    break;
                }
            }
            const dependencies = extractAlertDependencies(workflow?.workflow_raw);
            setAlertDependencies(dependencies);
            setIsAlertTriggerModalOpen(true);
            return;
        }
        // else, manual trigger, just run it
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
            dependencies: alertDependencies
        }
    }

    return {
        handleRunClick,
        isRunning,
        getTriggerModalProps,
        isRunButtonDisabled,
        message
    }
};
