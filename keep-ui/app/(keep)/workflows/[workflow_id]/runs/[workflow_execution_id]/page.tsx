import React from "react";
import { Metadata } from "next";
import { WorkflowExecutionResults } from "@/features/workflow-execution-results";

export default function WorkflowExecutionPage({
  params,
}: {
  params: { workflow_id: string; workflow_execution_id: string };
}) {
  return (
    <WorkflowExecutionResults
      workflowId={params.workflow_id}
      workflowExecutionId={params.workflow_execution_id}
    />
  );
}

export const metadata: Metadata = {
  title: "Workflow Execution Results",
};
