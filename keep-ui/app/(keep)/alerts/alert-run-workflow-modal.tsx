import { Button, Select, SelectItem } from "@tremor/react";
import { AlertDto } from "@/entities/alerts/model";
import Modal from "@/components/ui/Modal";
import { useWorkflows } from "utils/hooks/useWorkflows";
import { useState } from "react";
import { toast } from "react-toastify";
import { useRouter } from "next/navigation";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";

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
  const api = useApi();
  const { data: workflows } = useWorkflows({});
  const router = useRouter();

  const isOpen = !!alert;

  const clearAndClose = () => {
    setSelectedWorkflowId(undefined);
    handleClose();
  };

  const handleRun = async () => {
    try {
      const responseData = await api.post(
        `/workflows/${selectedWorkflowId}/run`,
        alert
      );

      // Workflow started successfully
      toast.success("Workflow started successfully", { position: "top-left" });
      const { workflow_execution_id } = responseData;
      router.push(
        `/workflows/${selectedWorkflowId}/runs/${workflow_execution_id}`
      );
    } catch (error) {
      showErrorToast(error, "Failed to start workflow");
    } finally {
      clearAndClose();
    }
  };

  return (
    <Modal onClose={clearAndClose} isOpen={isOpen} className="overflow-visible">
      {workflows && (
        <Select
          value={selectedWorkflowId}
          onValueChange={setSelectedWorkflowId}
        >
          {workflows
            .filter((workflow) => !workflow.disabled)
            .map((workflow) => {
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
