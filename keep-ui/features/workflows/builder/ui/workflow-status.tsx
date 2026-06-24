import { Callout } from "@tremor/react";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/24/outline";
import { useTranslations } from "next-intl";
import { useWorkflowStore } from "@/entities/workflows";
import clsx from "clsx";
import { ValidationError } from "@/entities/workflows/lib/validate-definition";
import { useState } from "react";

function ErrorList({
  validationErrors,
  onErrorClick,
}: {
  validationErrors: Record<string, ValidationError>;
  onErrorClick: (id: string) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const errorCount = Object.keys(validationErrors).length;
  const textSummary = `${errorCount} error${errorCount === 1 ? "" : "s"}`;

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        className="text-sm font-medium text-left hover:underline"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {isExpanded ? "▼" : "▶"} {textSummary}
      </button>
      {isExpanded && (
        <div className="flex flex-col gap-1 pl-2">
          {Object.entries(validationErrors).map(([id, error]) => (
            <span key={id}>
              {!id.startsWith("workflow_") && (
                <span
                  className="font-medium hover:underline cursor-pointer"
                  onClick={() => onErrorClick(id)}
                >
                  {id}:
                </span>
              )}{" "}
              {error[0]}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export const WorkflowStatus = ({ className }: { className?: string }) => {
  const t = useTranslations("workflows.status");
  const {
    validationErrors,
    canDeploy,
    nodes,
    edges,
    setSelectedNode,
    setSelectedEdge,
  } = useWorkflowStore();

  const handleErrorClick = (id: string) => {
    if (id === "trigger_end") {
      const addStepEdge = edges.find((edge) => edge.source === "trigger_end");
      if (addStepEdge) {
        setSelectedEdge(addStepEdge.id);
      }
    } else if (id === "trigger_start") {
      const addTriggerEdge = edges.find(
        (edge) => edge.source === "trigger_start"
      );
      if (addTriggerEdge) {
        setSelectedEdge(addTriggerEdge.id);
      }
    } else {
      const node = nodes.find(
        (node) => node.id === id || node.data.name === id
      );
      if (node) {
        setSelectedNode(node.id);
      }
    }
  };

  if (Object.keys(validationErrors).length === 0) {
    return (
      <Callout
        className={clsx("rounded p-2 text-sm", className)}
        title={t("workflowIsValid")}
        icon={CheckCircleIcon}
        color="teal"
      >
        {t("canBeDeployedAndRun")}
      </Callout>
    );
  }
  if (canDeploy) {
    return (
      <div
        className={clsx(
          "rounded p-2 text-sm",
          "bg-yellow-50 border border-yellow-200 text-yellow-800",
          className
        )}
      >
        <div className="flex items-center gap-2 font-medium">
          <ExclamationTriangleIcon className="h-5 w-5" />
          {t("workflowHasErrors")}
        </div>
        <div className="mt-1">{t("canBeSavedFixErrors")}</div>
        <ErrorList
          validationErrors={validationErrors}
          onErrorClick={handleErrorClick}
        />
      </div>
    );
  }
  return (
    <div
      className={clsx(
        "rounded p-2 text-sm",
        "bg-red-50 border border-red-200 text-red-800",
        className
      )}
    >
      <div className="flex items-center gap-2 font-medium">
        <ExclamationCircleIcon className="h-5 w-5" />
        {t("fixErrorsBeforeSaving")}
      </div>
      <ErrorList
        validationErrors={validationErrors}
        onErrorClick={handleErrorClick}
      />
    </div>
  );
};
