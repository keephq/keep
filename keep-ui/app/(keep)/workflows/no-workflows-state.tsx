"use client";

import { WorkflowTemplates } from "./workflow-templates";
import { InitialFacetsData } from "@/features/filter/api";
import { useRouter } from "next/navigation";
import { Button } from "@tremor/react";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowUpOnSquareStackIcon } from "@heroicons/react/24/outline";
import { UploadWorkflowsModal } from "./upload-workflows-modal";
import { PageTitle } from "@/shared/ui";

export function NoWorkflowsState({}: {
  initialFacetsData?: InitialFacetsData;
}) {
  const t = useTranslations("workflows");
  const [isUploadWorkflowsModalOpen, setIsUploadWorkflowsModalOpen] =
    useState(false);
  const router = useRouter();

  return (
    <div data-testid="no-workflows-state">
      <div className="mb-3">
        <PageTitle className="mb-3">{t("createYourFirstWorkflow")}</PageTitle>
        <p className="text-gray-700 mb-2">{t("chooseWorkflowTemplate")}</p>
        <div className="flex items-center gap-2">
          <span>{t("youCanAlso")}</span>
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
            {t("uploadWorkflows")}
          </Button>
          <span>{t("or")}</span>
          <Button
            color="orange"
            size="xs"
            variant="primary"
            onClick={() => router.push("/workflows/builder")}
          >
            {t("startFromScratch")}
          </Button>
        </div>
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
