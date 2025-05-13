"use client";

import { WorkflowTemplates } from "./workflow-templates";
import { InitialFacetsData } from "@/features/filter/api";
import { useRouter } from "next/navigation";
import { Button } from "@tremor/react";
import { useState } from "react";
import { ArrowUpOnSquareStackIcon } from "@heroicons/react/24/outline";
import { UploadWorkflowsModal } from "./upload-workflows-modal";
import { PageSubtitle, PageTitle } from "@/shared/ui";

export function NoWorkflowsState({}: {
  initialFacetsData?: InitialFacetsData;
}) {
  const [isUploadWorkflowsModalOpen, setIsUploadWorkflowsModalOpen] =
    useState(false);
  const router = useRouter();

  return (
    <div data-testid="no-workflows-state">
      <div className="mb-3">
        <PageTitle className="mb-3">Create your first workflow</PageTitle>
        <PageSubtitle>
          <div className="flex flex-col gap-2">
            <p>
              Choose a workflow template to start building the automation for
              your alerts and incidents.
            </p>
            <div className="flex items-center gap-2">
              <span>You can also</span>
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
                Upload Workflows
              </Button>
              <span>or</span>
              <Button
                color="orange"
                size="xs"
                variant="primary"
                onClick={() => router.push("/workflows/builder")}
              >
                Start from scratch
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
