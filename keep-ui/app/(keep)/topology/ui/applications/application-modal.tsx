import { CreateOrUpdateApplicationForm } from "@/app/(keep)/topology/ui/applications/create-or-update-application-form";
import Modal from "@/components/ui/Modal";
import { TopologyApplication } from "@/app/(keep)/topology/model";

type BaseProps = {
  isOpen: boolean;
  onClose: () => void;
};

type ApplicationModalCreateProps = BaseProps & {
  actionType: "create";
  application?: Partial<TopologyApplication>;
  onSubmit: (application: Omit<TopologyApplication, "id">) => Promise<void>;
  onDelete?: undefined;
};

type ApplicationModalEditProps = BaseProps & {
  actionType: "edit";
  application: TopologyApplication;
  onSubmit: (application: TopologyApplication) => Promise<void>;
  onDelete: () => void;
};

export function ApplicationModal({
  actionType,
  isOpen,
  application,
  onDelete,
  onClose,
  onSubmit,
}: ApplicationModalCreateProps | ApplicationModalEditProps) {
  const title =
    actionType === "create" ? "Create application" : "Edit application";

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      {actionType === "create" ? (
        <CreateOrUpdateApplicationForm
          action="create"
          application={application}
          onSubmit={onSubmit}
          onCancel={onClose}
        />
      ) : (
        <CreateOrUpdateApplicationForm
          action={actionType}
          application={application}
          onSubmit={onSubmit}
          onCancel={onClose}
          onDelete={onDelete}
        />
      )}
    </Modal>
  );
}
