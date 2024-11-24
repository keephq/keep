import { Button, Select, SelectItem } from "@tremor/react";
import { AlertDto } from "./models";
import Modal from "@/components/ui/Modal";
import { useWorkflows } from "utils/hooks/useWorkflows";
import { useState } from "react";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useApiUrl, useConfig } from "utils/hooks/useConfig";
import { toast } from "react-toastify";
import { useRouter } from "next/navigation";
import { ReadOnlyAwareToaster } from "@/shared/lib/ReadOnlyAwareToaster";

interface Props {
  alert: AlertDto | null | undefined;
  handleClose: () => void;
}

export default function AlertRunWorkflowModal({ alert, handleClose }: Props) {
  /**
   *
   */
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<
    string | undefined
  >(undefined);
  const { data: workflows } = useWorkflows({});
  const { data: session } = useSession();
  const router = useRouter();
  const apiUrl = useApiUrl();
  const { data: configData } = useConfig();

  const isOpen = !!alert;

  const clearAndClose = () => {
    setSelectedWorkflowId(undefined);
    handleClose();
  };

  const handleRun = async () => {
    const response = await fetch(
      `${apiUrl}/workflows/${selectedWorkflowId}/run`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(alert),
      }
    );

    if (response.ok) {
      // Workflow started successfully
      toast.success("Workflow started successfully", { position: "top-left" });
      const responseData = await response.json();
      const { workflow_execution_id } = responseData;
      router.push(
        `/workflows/${selectedWorkflowId}/runs/${workflow_execution_id}`
      );
    } else {
      ReadOnlyAwareToaster.error("Failed to start workflow", configData, { position: "top-left" });
    }
    clearAndClose();
  };

  return (
    <Modal onClose={clearAndClose} isOpen={isOpen} className="overflow-visible">
      {workflows && (
        <Select
          value={selectedWorkflowId}
          onValueChange={setSelectedWorkflowId}
        >
          {workflows.map((workflow) => {
            return (
              <SelectItem key={workflow.id} value={workflow.id}>
                {workflow.description}
              </SelectItem>
            );
          })}
        </Select>
      )}
      <Button
        onClick={handleRun}
        color="orange"
        className="mt-2.5"
        disabled={!selectedWorkflowId}
      >
        Run
      </Button>
    </Modal>
  );
}
