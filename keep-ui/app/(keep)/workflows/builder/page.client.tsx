"use client";

import { Title, Button } from "@tremor/react";
import { useEffect, useRef, useState } from "react";
import {
  PlusIcon,
  BoltIcon,
  ArrowUpOnSquareIcon,
  PlayIcon,
  PencilIcon,
} from "@heroicons/react/20/solid";
import { BuilderCard } from "./builder-card";
import { loadWorkflowYAML } from "./utils";
import { showErrorToast } from "@/shared/ui";
import { YAMLException } from "js-yaml";
import useStore from "./builder-store";
import BuilderMetadataModal from "./builder-metadata-modal";
import { Workflow } from "@/shared/api/workflows";

export function WorkflowBuilderPageClient({
  workflowRaw: workflow,
  workflowId,
}: {
  workflowRaw?: string;
  workflowId?: string;
}) {
  const [fileContents, setFileContents] = useState<string | null>("");
  const [fileName, setFileName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const {
    buttonsEnabled,
    triggerGenerate,
    triggerSave,
    triggerRun,
    isSaving,
    v2Properties,
    updateV2Properties,
  } = useStore();

  const isValid = useStore((state) => state.definition.isValid);
  const isInitialized = useStore((state) => !!state.workflowId);

  useEffect(() => {
    setFileContents(null);
    setFileName("");
  }, []);

  function loadWorkflow() {
    document.getElementById("workflowFile")?.click();
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
    <main className="mx-auto max-w-full h-[98%]">
      <div className="flex justify-between">
        <div className="flex flex-col">
          <Title>{workflowId ? "Edit" : "New"} Workflow</Title>
        </div>
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
            disabled={!isValid || isSaving}
            onClick={() => triggerSave()}
          >
            {isSaving ? "Saving..." : "Save & Deploy"}
          </Button>
          {!workflow && (
            <Button
              disabled={!isValid}
              color="orange"
              size="md"
              className="min-w-28"
              icon={BoltIcon}
              onClick={() => triggerGenerate()}
            >
              Get YAML
            </Button>
          )}
        </div>
      </div>
      <BuilderCard
        fileContents={fileContents}
        workflow={workflow}
        workflowId={workflowId}
      />
      <BuilderMetadataModal
        workflow={
          {
            name: v2Properties?.name || "",
            description: v2Properties?.description || "",
          } as Workflow
        }
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        onSubmit={handleMetadataSubmit}
      />
    </main>
  );
}
