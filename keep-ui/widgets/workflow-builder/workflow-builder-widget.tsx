"use client";

import { Button, Title } from "@tremor/react";
import { useRef, useState } from "react";
import {
  ArrowUpOnSquareIcon,
  PencilIcon,
  PlayIcon,
  PlusIcon,
} from "@heroicons/react/20/solid";
import { WorkflowBuilderCard } from "./workflow-builder-card";
import { showErrorToast } from "@/shared/ui";
import { useWorkflowStore } from "@/entities/workflows";
import { WorkflowMetadataModal } from "@/features/workflows/edit-metadata";
import { WorkflowTestRunModal } from "@/features/workflows/test-run";
import { WorkflowEnabledSwitch } from "@/features/workflows/enable-disable";
import { WorkflowSyncStatus } from "@/app/(keep)/workflows/[workflow_id]/workflow-sync-status";
import { parseWorkflowYamlStringToJSON } from "@/entities/workflows/lib/reorderWorkflowSections";
import clsx from "clsx";

export interface WorkflowBuilderWidgetProps {
  workflowRaw: string | undefined;
  workflowId: string | undefined;
  standalone?: boolean;
}

export function WorkflowBuilderWidget({
  workflowRaw,
  workflowId,
  standalone,
}: WorkflowBuilderWidgetProps) {
  const [fileContents, setFileContents] = useState<string | null>(null);
  const [fileName, setFileName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const {
    triggerSave,
    triggerRun,
    updateV2Properties,
    isInitialized,
    isEditorSyncedWithNodes,
    canDeploy,
    isSaving,
    v2Properties,
  } = useWorkflowStore();

  const isValid = useWorkflowStore((state) => !!state.definition?.isValid);

  function loadWorkflow() {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  }

  function createNewWorkflow() {
    const confirmed = confirm(
      "Are you sure you want to create a new workflow?"
    );
    if (confirmed) {
      window.location.reload();
    }
  }

  function handleFileChange(event: any) {
    const file = event.target.files[0];
    const fName = event.target.files[0].name;
    const reader = new FileReader();
    reader.onload = (event) => {
      setFileName(fName);
      const contents = event.target!.result as string;
      try {
        const _ = parseWorkflowYamlStringToJSON(contents);
        setFileContents(contents);
      } catch (error) {
        showErrorToast(error, "Failed to parse workflow");
        setFileName("");
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    };
    reader.readAsText(file);
  }

  const handleMetadataSubmit = ({
    name,
    description,
  }: {
    name: string;
    description: string;
  }) => {
    updateV2Properties({ name, description });
    setIsEditModalOpen(false);
    // Properties are now synced immediately in the store
    triggerSave();
  };

  return (
    <>
      <main className="mx-auto max-w-full flex flex-col h-full">
        <div className="flex items-baseline justify-between p-2">
          <div className="flex items-center gap-2">
            <Title className={clsx(workflowId ? "mx-2" : "mx-0")}>
              {workflowId ? "Edit" : "New"} Workflow
            </Title>
            <WorkflowSyncStatus />
          </div>
          <div className="flex gap-2">
            {!workflowRaw && (
              <>
                <Button
                  color="orange"
                  size="md"
                  onClick={createNewWorkflow}
                  icon={PlusIcon}
                  className="min-w-28"
                  variant="secondary"
                  disabled={!isInitialized}
                >
                  New
                </Button>
                <Button
                  color="orange"
                  size="md"
                  onClick={loadWorkflow}
                  className="min-w-28"
                  variant="secondary"
                  icon={ArrowUpOnSquareIcon}
                  disabled={!isInitialized}
                >
                  Load
                </Button>
                <input
                  type="file"
                  id="workflowFile"
                  style={{ display: "none" }}
                  ref={fileInputRef}
                  onChange={handleFileChange}
                />
              </>
            )}
            {isInitialized && <WorkflowEnabledSwitch />}
            {workflowRaw && (
              <Button
                color="orange"
                size="md"
                onClick={() => setIsEditModalOpen(true)}
                icon={PencilIcon}
                className="min-w-28"
                variant="secondary"
                disabled={!isInitialized}
              >
                Edit Metadata
              </Button>
            )}
            <Button
              color="orange"
              size="md"
              className="min-w-28 disabled:opacity-70"
              icon={PlayIcon}
              disabled={!isValid}
              onClick={() => triggerRun()}
            >
              Test Run
            </Button>
            <Button
              color="orange"
              size="md"
              className="min-w-28 relative disabled:opacity-70"
              icon={ArrowUpOnSquareIcon}
              disabled={!canDeploy || isSaving || !isEditorSyncedWithNodes}
              onClick={() => triggerSave()}
              data-testid="wf-builder-main-save-deploy-button"
            >
              {isSaving ? "Saving..." : "Save"}
            </Button>
          </div>
        </div>
        <WorkflowBuilderCard
          fileContents={fileContents}
          workflowRaw={workflowRaw}
          workflowId={workflowId}
          standalone={standalone}
        />
      </main>
      <WorkflowTestRunModal workflowId={workflowId ?? ""} />
      <WorkflowMetadataModal
        isOpen={isEditModalOpen}
        workflow={{
          name: v2Properties?.name || "",
          description: v2Properties?.description || "",
        }}
        onClose={() => setIsEditModalOpen(false)}
        onSubmit={handleMetadataSubmit}
      />
    </>
  );
}
