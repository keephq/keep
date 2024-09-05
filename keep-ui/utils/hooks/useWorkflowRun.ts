import { WorkflowExecutionFailure, WorkflowExecution } from "app/workflows/builder/types";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { getApiURL } from "utils/apiUrl";

export const useWorkflowRun = (workflowRaw: string) => {
    const [runningWorkflowExecution, setRunningWorkflowExecution] = useState<
    WorkflowExecution | WorkflowExecutionFailure | null
  >(null);
    const [runModalOpen, setRunModalOpen] = useState(false);
    const [loading, setLoading] = useState(true);
    const { data: session, status, update } = useSession();
    const accessToken = session?.accessToken;

    const apiUrl = getApiURL();
    const url = `${apiUrl}/workflows/test`;
    const method = "POST";
    const headers = {
        "Content-Type": "text/html",
        Authorization: `Bearer ${accessToken}`,
    };

    useEffect(() => {
        if (runModalOpen) {
            const body = workflowRaw;
            setLoading(true);
            fetch(url, { method, headers, body })
                .then((response) => {
                    if (response.ok) {
                        response.json().then((data) => {
                            setRunningWorkflowExecution({
                                ...data,
                            });
                        });
                    } else {
                        response.json().then((data) => {
                            setRunningWorkflowExecution({
                                error: data?.detail ?? "Unknown error",
                            });
                        });
                    }
                })
                .catch((error) => {
                    alert(`Error: ${error}`);
                    setRunModalOpen(false);
                }).finally(()=>{
                    setLoading(false);
                })
        }
    }, [workflowRaw, runModalOpen])

    return {
        loading,
        runModalOpen,
        setRunModalOpen,
        runningWorkflowExecution,
        setRunningWorkflowExecution,
    }
};
