import Modal from "@/components/ui/Modal";
import "react-loading-skeleton/dist/skeleton.css";
import { WorkflowTemplates } from "./workflow-templates";
import { useRouter } from "next/navigation";
import { Button } from "@tremor/react";
import { useTranslations } from "next-intl";
import { PageSubtitle } from "@/shared/ui";

interface CreateWorkflowModalProps {
  onClose: () => void;
}

export const CreateWorkflowModal: React.FC<CreateWorkflowModalProps> = ({
  onClose,
}) => {
  const t = useTranslations("workflows.createModal");
  const router = useRouter();

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      className="min-w-[80vw] min-h-[90vh] max-h-[90vh]"
      title={t("createWorkflow")}
    >
      <div className="flex flex-col min-h-0 max-w-full max-h-full overflow-hidden">
        <PageSubtitle>
          <div className="flex flex-col gap-2 mb-3 h-full w-full">
            <p>
              {t("chooseWorkflowTemplate")}
            </p>
            <p>
              {t("orSkipAnd")}{" "}
              <Button
                className="ml-2"
                color="orange"
                size="xs"
                variant="primary"
                onClick={() => router.push("/workflows/builder")}
              >
                {t("startFromScratch")}
              </Button>
            </p>
          </div>
        </PageSubtitle>
        <WorkflowTemplates></WorkflowTemplates>
      </div>
    </Modal>
  );
};
