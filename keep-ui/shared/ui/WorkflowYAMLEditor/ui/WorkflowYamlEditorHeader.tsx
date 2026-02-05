import { WorkflowSyncStatus } from "@/app/(keep)/workflows/[workflow_id]/workflow-sync-status";
import { Title } from "@tremor/react";
import clsx from "clsx";

interface WorkflowYamlEditorHeaderProps {
  workflowId: string | null;
  isInitialized: boolean;
  lastDeployedAt: number | null;
  hasChanges: boolean;
  children: React.ReactNode;
}

export function WorkflowYamlEditorHeader({
  workflowId,
  hasChanges,
  isInitialized,
  lastDeployedAt,
  children,
}: WorkflowYamlEditorHeaderProps) {
  return (
    <div className="flex items-baseline justify-between p-2 border-b border-gray-200">
      <div className="flex items-center gap-2">
        <Title className={clsx(workflowId ? "mx-2" : "mx-0")}>
          {workflowId ? "Edit" : "New"} Workflow
        </Title>
        <WorkflowSyncStatus
          workflowId={workflowId}
          isInitialized={isInitialized}
          lastDeployedAt={lastDeployedAt}
          isChangesSaved={!hasChanges}
        />
      </div>
      <div className="flex gap-2">{children}</div>
    </div>
  );
}
