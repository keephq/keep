import { Button, Select, SelectItem, Title } from "@tremor/react";

import Modal from "@/components/ui/Modal";
import { useWorkflows } from "utils/hooks/useWorkflows";
import { useState } from "react";
import { toast } from "react-toastify";
import { useRouter } from "next/navigation";
import { IncidentDto } from "@/entities/incidents/model";
import { AlertDto } from "@/app/(keep)/alerts/models";
import { useApi } from "@/shared/lib/hooks/useApi";

interface Props {
  alert?: AlertDto | null | undefined;
  incident?: IncidentDto | null | undefined;
  handleClose: () => void;
}

export default function ManualRunWorkflowModal({
  alert,
  incident,
  handleClose,
}: Props) {
  /**
   *
   */
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<
    string | undefined
  >(undefined);
  const { data: workflows } = useWorkflows({});
  const api = useApi();
  const router = useRouter();

  const isOpen = !!alert || !!incident;

  const clearAndClose = () => {
    setSelectedWorkflowId(undefined);
    handleClose();
  };

  const handleRun = async () => {
    try {
      const responseData = await api.post(
        `/workflows/${selectedWorkflowId}/run`,
        {
          type: alert ? "alert" : "incident",
          body: alert ? alert : incident,
        }
      );

      // Workflow started successfully
      toast.success("Workflow started successfully", { position: "top-left" });
      const { workflow_execution_id } = responseData;
      router.push(
        `/workflows/${selectedWorkflowId}/runs/${workflow_execution_id}`
      );
    } catch (error) {
      toast.error("Failed to start workflow", { position: "top-left" });
    }
    clearAndClose();
  };

  return (
    <Modal onClose={clearAndClose} isOpen={isOpen} className="overflow-visible">
      <Title className="mb-1">Select workflow to run</Title>
      {workflows ? (
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
      ) : (
        <div>No workflows found</div>
      )}
      <div className="flex justify-end gap-2 mt-4">
        <Button onClick={clearAndClose} color="orange" variant="secondary">
          Cancel
        </Button>
        <Button
          onClick={handleRun}
          color="orange"
          disabled={!selectedWorkflowId}
        >
          Run
        </Button>
      </div>
    </Modal>
  );
}
