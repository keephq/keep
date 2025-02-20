import { Callout } from "@tremor/react";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/24/outline";
import { useWorkflowStore } from "@/entities/workflows";
import clsx from "clsx";

export const WorkflowStatus = ({ className }: { className?: string }) => {
  const { validationErrors, canDeploy, setSelectedNode } = useWorkflowStore();
  return Object.keys(validationErrors).length > 0 ? (
    <Callout
      className={clsx("rounded p-2", className)}
      title={
        canDeploy
          ? "Fix errors to run workflow"
          : "Fix the errors before saving"
      }
      icon={ExclamationCircleIcon}
      color="rose"
    >
      {Object.entries(validationErrors).map(([id, error]) => (
        <span key={id}>
          <span
            className="font-medium hover:underline cursor-pointer"
            onClick={() => {
              // TODO: fix this, to handle case with steps, where name used as id
              // setSelectedNode(id);
            }}
          >
            {id}:
          </span>{" "}
          {error}
        </span>
      ))}
    </Callout>
  ) : (
    <Callout
      className={clsx("rounded p-2", className)}
      title="Schema is valid"
      icon={CheckCircleIcon}
      color="teal"
    >
      Workflow can be deployed and run
    </Callout>
  );
};
