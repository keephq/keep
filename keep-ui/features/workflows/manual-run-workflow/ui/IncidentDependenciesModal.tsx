import Modal from "@/components/ui/Modal";
import { WorkflowAlertIncidentDependenciesForm } from "../../test-run/ui/workflow-alert-incident-dependencies-form";

export function IncidentDependenciesModal({
  isOpen,
  onClose,
  onSubmit,
  dependencies,
  staticFields,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: any) => void;
  dependencies: string[];
  staticFields: any[];
}) {
  return (
    <Modal
      className="max-w-5xl"
      isOpen={isOpen}
      onClose={onClose}
      title="Run Workflow"
    >
      <WorkflowAlertIncidentDependenciesForm
        type="incident"
        dependencies={dependencies}
        staticFields={staticFields}
        onCancel={onClose}
        onSubmit={(payload) => {
          onSubmit(payload);
          onClose();
        }}
        submitLabel="Run Workflow"
      />
    </Modal>
  );
}
