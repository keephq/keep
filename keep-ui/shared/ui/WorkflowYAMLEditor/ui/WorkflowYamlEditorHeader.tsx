import { WorkflowSyncStatus } from "@/app/(keep)/workflows/[workflow_id]/workflow-sync-status";
import { PlayIcon } from "@heroicons/react/20/solid";
import { Button, Title } from "@tremor/react";
import clsx from "clsx";

interface WorkflowYamlEditorHeaderProps {
  workflowId: string | undefined;
  isInitialized: boolean;
  lastDeployedAt: number | null;
  isValid: boolean;
  isSaving: boolean;
  hasChanges: boolean;
  onRun: () => void;
  onSave: () => void;
}

export function WorkflowYamlEditorHeader({
  workflowId,
  isValid,
  isSaving,
  hasChanges,
  isInitialized,
  lastDeployedAt,
  onRun,
  onSave,
}: WorkflowYamlEditorHeaderProps) {
  return (
    <div className="flex items-baseline justify-between p-2 border-b border-gray-200">
      <div className="flex items-center gap-2">
        <Title className={clsx(workflowId ? "mx-2" : "mx-0")}>
          {workflowId ? "Edit" : "New"} Workflow
        </Title>
        <WorkflowSyncStatus
          isInitialized={isInitialized}
          lastDeployedAt={lastDeployedAt}
          isChangesSaved={!hasChanges}
        />
      </div>
      <div className="flex gap-2">
        <Button
          color="orange"
          size="sm"
          className="min-w-28 disabled:opacity-70"
          icon={PlayIcon}
          disabled={!isValid}
          onClick={onRun}
          data-testid="wf-builder-main-test-run-button"
        >
          Test Run
        </Button>
        <Button
          color="orange"
          size="sm"
          className="min-w-28 relative disabled:opacity-70"
          disabled={!hasChanges || isSaving}
          onClick={onSave}
          data-testid="wf-builder-main-save-deploy-button"
        >
          {isSaving ? "Saving..." : "Save"}
        </Button>
      </div>
    </div>
  );
}
