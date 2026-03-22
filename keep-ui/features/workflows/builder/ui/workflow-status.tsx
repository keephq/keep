import { Callout } from "@tremor/react";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/24/outline";
import { useWorkflowStore } from "@/entities/workflows";
import clsx from "clsx";
import { ValidationError } from "@/entities/workflows/lib/validate-definition";
import { useI18n } from "@/i18n/hooks/useI18n";

function ErrorList({
  validationErrors,
  onErrorClick,
}: {
  validationErrors: Record<string, ValidationError>;
  onErrorClick: (id: string) => void;
}) {
  const { t } = useI18n();
  const textSummary = t("workflows.builder.errorCount", {
    count: Object.keys(validationErrors).length,
  });
  return (
    <details className="flex flex-col gap-1">
      <summary className="text-sm font-medium">{textSummary}</summary>
      <span className="flex flex-col gap-1">
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
      </span>
    </details>
  );
}

export const WorkflowStatus = ({ className }: { className?: string }) => {
  const {
    validationErrors,
    canDeploy,
    nodes,
    edges,
    setSelectedNode,
    setSelectedEdge,
  } = useWorkflowStore();
  const { t } = useI18n();

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
        title={t("workflows.builder.workflowValid")}
        icon={CheckCircleIcon}
        color="teal"
      >
        {t("workflows.builder.workflowValidDescription")}
      </Callout>
    );
  }
  if (canDeploy) {
    return (
      <Callout
        className={clsx("rounded p-2 text-sm", className)}
        title={t("workflows.builder.workflowHasErrors")}
        icon={ExclamationTriangleIcon}
        color="yellow"
      >
        {t("workflows.builder.workflowHasErrorsDescription")}
        {/* TODO: fix In HTML, <summary> cannot be a descendant of <p>. */}
        <ErrorList
          validationErrors={validationErrors}
          onErrorClick={handleErrorClick}
        />
      </Callout>
    );
  }
  return (
    <Callout
      className={clsx("rounded p-2 text-sm", className)}
      title={t("workflows.builder.fixErrorsBeforeSaving")}
      icon={ExclamationCircleIcon}
      color="rose"
    >
      <ErrorList
        validationErrors={validationErrors}
        onErrorClick={handleErrorClick}
      />
    </Callout>
  );
};
