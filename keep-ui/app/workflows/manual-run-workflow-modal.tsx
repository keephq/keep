import {Button, Select, SelectItem, Title} from "@tremor/react";

import Modal from "@/components/ui/Modal";
import { useWorkflows } from "utils/hooks/useWorkflows";
import { useState } from "react";
import { useSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import { toast } from "react-toastify";
import { useRouter } from "next/navigation";
import { IncidentDto } from "@/app/incidents/models";
import { AlertDto } from "@/app/alerts/models";

interface Props {
  alert?: AlertDto | null | undefined;
  incident?: IncidentDto | null | undefined;
  handleClose: () => void;
}

export default function ManualRunWorkflowModal({ alert, incident, handleClose }: Props) {
  /**
   *
   */
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<
    string | undefined
  >(undefined);
  const { data: workflows } = useWorkflows({});
  const { data: session } = useSession();
  const router = useRouter();
  const apiUrl = getApiURL();

  const isOpen = !!alert || !!incident;

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
        body: JSON.stringify({"type": alert ? "alert" : "incident", "body": alert ? alert : incident}),
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
      toast.error("Failed to start workflow", { position: "top-left" });
    }
    clearAndClose();
  };

  return (
    <Modal onClose={clearAndClose} isOpen={isOpen} className="overflow-visible">
      <Title className="mb-1">Select Workflow to run</Title>
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
