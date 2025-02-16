"use client";

import { Button, Title } from "@tremor/react";
import { useRef, useState } from "react";
import {
  ArrowUpOnSquareIcon,
  PencilIcon,
  PlayIcon,
  PlusIcon,
} from "@heroicons/react/20/solid";
import { BuilderCard } from "./builder-card";
import { showErrorToast } from "@/shared/ui";
import { YAMLException } from "js-yaml";
import { useWorkflowStore } from "@/entities/workflows";
import { loadWorkflowYAML } from "@/entities/workflows/lib/parser";
import { WorkflowMetadataModal } from "@/features/workflows/edit-metadata";
import { WorkflowTestRunModal } from "@/features/workflows/test-run";
import { WorkflowEnabledSwitch } from "@/features/workflows/enable-disable";

export function WorkflowBuilderWidget({
  workflowRaw: workflow,
  workflowId,
  standalone = false,
}: {
  workflowRaw?: string;
  workflowId?: string;
  standalone?: boolean;
}) {
  const [fileContents, setFileContents] = useState<string | null>(null);
  const [fileName, setFileName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const {
    canDeploy,
    buttonsEnabled,
    triggerSave,
    triggerRun,
    isSaving,
    v2Properties,
    updateV2Properties,
  } = useWorkflowStore();

  const isValid = useWorkflowStore((state) => !!state.definition?.isValid);
  const isInitialized = useWorkflowStore((state) => !!state.workflowId);

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
        const parsedWorkflow = loadWorkflowYAML(contents);
        setFileContents(contents);
      } catch (error) {
        if (error instanceof YAMLException) {
          showErrorToast(error, "Invalid YAML: " + error.message);
        } else {
          showErrorToast(error, "Failed to load workflow");
        }
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
          <Title className="mx-2">{workflowId ? "Edit" : "New"} Workflow</Title>
          <div className="flex gap-2">
            {!workflow && (
              <>
                <Button
                  color="orange"
                  size="md"
                  onClick={createNewWorkflow}
                  icon={PlusIcon}
                  className="min-w-28"
                  variant="secondary"
                  disabled={!buttonsEnabled}
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
                  disabled={!buttonsEnabled}
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
            {workflow && (
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
              className="min-w-28"
              icon={PlayIcon}
              disabled={!isValid}
              onClick={() => triggerRun()}
            >
              Test Run
            </Button>
            <Button
              color="orange"
              size="md"
              className="min-w-28"
              icon={ArrowUpOnSquareIcon}
              disabled={!canDeploy || isSaving}
              onClick={() => triggerSave()}
              data-testid="wf-builder-main-save-deploy-button"
            >
              {isSaving ? "Saving..." : "Save & Deploy"}
            </Button>
          </div>
        </div>
        <BuilderCard
          fileContents={fileContents}
          workflow={workflow}
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
