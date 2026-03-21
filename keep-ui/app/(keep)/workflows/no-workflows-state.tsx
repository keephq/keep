"use client";

import { WorkflowTemplates } from "./workflow-templates";
import { InitialFacetsData } from "@/features/filter/api";
import { useRouter } from "next/navigation";
import { Button } from "@tremor/react";
import { useState } from "react";
import { ArrowUpOnSquareStackIcon } from "@heroicons/react/24/outline";
import { UploadWorkflowsModal } from "./upload-workflows-modal";
import { PageSubtitle, PageTitle } from "@/shared/ui";
import { useI18n } from "@/i18n/hooks/useI18n";

export function NoWorkflowsState({}: {
  initialFacetsData?: InitialFacetsData;
}) {
  const { t } = useI18n();
  const [isUploadWorkflowsModalOpen, setIsUploadWorkflowsModalOpen] =
    useState(false);
  const router = useRouter();

  return (
    <div data-testid="no-workflows-state">
      <div className="mb-3">
        <PageTitle className="mb-3">{t("workflows.messages.createFirstWorkflow")}</PageTitle>
        <PageSubtitle>
          <div className="flex flex-col gap-2">
            <p>
              {t("workflows.messages.chooseTemplateDescription")}
            </p>
            <div className="flex items-center gap-2">
              <span>{t("workflows.messages.youCanAlso")}</span>
              <Button
                color="orange"
                size="xs"
                variant="secondary"
                onClick={() => {
                  setIsUploadWorkflowsModalOpen(true);
                }}
                icon={ArrowUpOnSquareStackIcon}
                id="uploadWorkflowButton"
              >
                {t("workflows.messages.uploadWorkflows")}
              </Button>
              <span>{t("workflows.messages.or")}</span>
              <Button
                color="orange"
                size="xs"
                variant="primary"
                onClick={() => router.push("/workflows/builder")}
              >
                {t("workflows.messages.startFromScratch")}
              </Button>
            </div>
          </div>
        </PageSubtitle>
      </div>
      <WorkflowTemplates></WorkflowTemplates>
      {isUploadWorkflowsModalOpen && (
        <UploadWorkflowsModal
          onClose={() => setIsUploadWorkflowsModalOpen(false)}
        />
      )}
    </div>
  );
}
