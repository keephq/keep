import { CloudIcon, ExclamationTriangleIcon } from "@heroicons/react/20/solid";
import { Tooltip } from "@/shared/ui";
import { useEffect } from "react";
import TimeAgo, { Formatter } from "react-timeago";
import { useWorkflowDetail } from "@/entities/workflows/model/useWorkflowDetail";

interface WorkflowSyncStatusProps {
  workflowId: string | null;
  isInitialized: boolean;
  lastDeployedAt: number | null;
  isChangesSaved: boolean;
}

export function WorkflowSyncStatus({
  workflowId,
  isInitialized,
  lastDeployedAt,
  isChangesSaved,
}: WorkflowSyncStatusProps) {
  const { workflow } = useWorkflowDetail(workflowId, null);

  const lastSavedAt = workflow?.last_updated + "Z" || lastDeployedAt;
  const revision = workflow?.revision;

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (!isChangesSaved) {
        e.preventDefault();
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => {
      window.removeEventListener("beforeunload", handler);
    };
  }, [isChangesSaved]);

  if (!isInitialized) {
    return null;
  }

  const customFormatter: Formatter = (
    value,
    unit,
    suffix,
    epochMiliseconds,
    nextFormatter
  ) => {
    if (unit === "second") {
      return "just now";
    }
    return nextFormatter?.(value, unit, suffix, epochMiliseconds);
  };

  return (
    <Tooltip content={isChangesSaved ? "Saved to Keep" : "Not saved"}>
      <span className="flex items-center gap-1 text-sm">
        {isChangesSaved ? (
          <>
            <CloudIcon className="size-5 text-gray-500" />
            <span className="text-gray-500">
              {revision && (
                <span data-testid="wf-revision">Revision {revision}</span>
              )}
              {revision ? ", saved " : "Saved "}
              {lastSavedAt ? (
                <TimeAgo date={lastSavedAt} formatter={customFormatter} />
              ) : (
                "to Keep"
              )}
            </span>
          </>
        ) : (
          <>
            <ExclamationTriangleIcon className="size-5 text-yellow-500" />
            <span className="text-yellow-600 font-bold">
              Changes are not saved
            </span>
          </>
        )}
      </span>
    </Tooltip>
  );
}
