import Modal from "@/components/ui/Modal";
import "react-loading-skeleton/dist/skeleton.css";
import { WorkflowTemplates } from "./workflow-templates";

interface CreateWorkflowModalProps {
  onClose: () => void;
}

export const CreateWorkflowModal: React.FC<CreateWorkflowModalProps> = ({
  onClose,
}) => {
  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      className="min-w-[80vw] min-h-[90vh]"
      title="Create workflow"
    >
      <WorkflowTemplates></WorkflowTemplates>
    </Modal>
  );
};
