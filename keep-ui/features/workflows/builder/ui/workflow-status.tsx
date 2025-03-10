import { Callout } from "@tremor/react";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/24/outline";
import { useWorkflowStore } from "@/entities/workflows";
import clsx from "clsx";

function ErrorList({
  validationErrors,
  onErrorClick,
}: {
  validationErrors: Record<string, string>;
  onErrorClick: (id: string) => void;
}) {
  const textSummary = `${Object.keys(validationErrors).length} error${
    Object.keys(validationErrors).length === 1 ? "" : "s"
  }`;
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
            {error}
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
        title="Workflow is valid"
        icon={CheckCircleIcon}
        color="teal"
      >
        It can be deployed and run
      </Callout>
    );
  }
  if (canDeploy) {
    return (
      <Callout
        className={clsx("rounded p-2 text-sm", className)}
        title="Workflow has errors"
        icon={ExclamationTriangleIcon}
        color="yellow"
      >
        It can be saved, but to run it, fix errors
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
      title="Fix the errors before saving"
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
