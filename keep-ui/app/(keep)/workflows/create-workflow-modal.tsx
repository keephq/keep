import { useI18n } from "@/i18n/hooks/useI18n";
import Modal from "@/components/ui/Modal";
import "react-loading-skeleton/dist/skeleton.css";
import { WorkflowTemplates } from "./workflow-templates";
import { useRouter } from "next/navigation";
import { Button } from "@tremor/react";
import { PageSubtitle } from "@/shared/ui";

interface CreateWorkflowModalProps {
  onClose: () => void;
}

export const CreateWorkflowModal: React.FC<CreateWorkflowModalProps> = ({
  onClose,
}) => {
  const router = useRouter();
  const { t } = useI18n();

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      className="min-w-[80vw] min-h-[90vh] max-h-[90vh]"
      title={t("workflows.createModal.title")}
    >
      <div className="flex flex-col min-h-0 max-w-full max-h-full overflow-hidden">
        <PageSubtitle>{t("workflows.createModal.chooseTemplate")}</PageSubtitle>
        <div className="mb-3 mt-2 flex flex-wrap items-center gap-2">
          <span>{t("workflows.createModal.orSkip")}</span>
          <Button
            color="orange"
            size="xs"
            variant="primary"
            onClick={() => router.push("/workflows/builder")}
          >
            {t("workflows.createModal.startFromScratch")}
          </Button>
        </div>
        <WorkflowTemplates></WorkflowTemplates>
      </div>
    </Modal>
  );
};
