import { useWorkflowStore } from "@/entities/workflows";
import { CloudIcon, ExclamationTriangleIcon } from "@heroicons/react/20/solid";
import { Tooltip } from "@/shared/ui";
import { useEffect } from "react";
import TimeAgo, { Formatter } from "react-timeago";

export function WorkflowSyncStatus() {
  const {
    lastChangedAt,
    lastDeployedAt,
    isEditorSyncedWithNodes,
    isInitialized,
  } = useWorkflowStore();
  const isChangesSaved =
    isEditorSyncedWithNodes && lastDeployedAt >= lastChangedAt;

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

  const formatter = (
    value: number,
    unit: string,
    suffix: string,
    epochMiliseconds: number,
    nextFormatter: any
  ) => {
    if (unit === "second") {
      return "just now";
    }
    return nextFormatter?.();
  };

  if (!isInitialized) {
    return null;
  }

  return (
    <Tooltip content={isChangesSaved ? "Saved to Keep" : "Not saved"}>
      <span className="flex items-center gap-1 text-sm">
        {isChangesSaved ? (
          <>
            <CloudIcon className="size-5 text-gray-500" />
            <span className="text-gray-500">
              Saved{" "}
              {lastDeployedAt ? (
                <TimeAgo date={lastDeployedAt} formatter={formatter} />
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
