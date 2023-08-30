import React from "react";
import { CircleStackIcon } from "@heroicons/react/24/outline";
import { Callout, Italic } from "@tremor/react";
import Link from "next/link";

const WorkflowsEmptyState = () => {
  const loadAlert = () => document.getElementById("workflowFile")?.click();

  return (
    <div className="text-center mt-4">
      <Callout
        title="No Workflows"
        icon={CircleStackIcon}
        color="yellow"
        className="mt-5"
      >
        You can start by uploading a workflow file using the{" "}
        <Italic onClick={loadAlert} className="underline cursor-pointer">
          Load a Workflow
        </Italic>{" "}
        button above or by using the{" "}
        <Italic className="underline">
          <Link href="/builder">Workflow Builder</Link>
        </Italic>{" "}
        to create a new workflow.
      </Callout>
    </div>
  );
};

export default WorkflowsEmptyState;
