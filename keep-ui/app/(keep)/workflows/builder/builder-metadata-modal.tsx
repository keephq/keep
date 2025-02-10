import Modal from "@/components/ui/Modal";
import { Workflow } from "@/shared/api/workflows";
import { EditWorkflowMetadataForm } from "./edit-workflow-metadata-form";

interface Props {
  workflow: Workflow;
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

export default function BuilderMetadataModal({
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
