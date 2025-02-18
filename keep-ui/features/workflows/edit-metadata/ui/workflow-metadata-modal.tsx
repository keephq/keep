import Modal from "@/components/ui/Modal";
import { EditWorkflowMetadataForm } from "./edit-workflow-metadata-form";
import { WorkflowMetadata } from "@/entities/workflows";

interface Props {
  workflow: WorkflowMetadata;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: ({
    name,
    description,
  }: {
    name: string;
    description: string;
  }) => void;
}

export function WorkflowMetadataModal({
  workflow,
  isOpen,
  onClose,
  onSubmit,
}: Props) {
  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <EditWorkflowMetadataForm
        workflow={workflow}
        onCancel={onClose}
        onSubmit={onSubmit}
      />
    </Modal>
  );
}
