import React from "react";
import { Metadata } from "next";
import { WorkflowExecutionResults } from "@/features/workflow-execution-results";

export default async function WorkflowExecutionPage(
  props: {
    params: Promise<{ workflow_id: string; workflow_execution_id: string }>;
  }
) {
  const params = await props.params;
  return (
    <WorkflowExecutionResults
      standalone
      workflowId={params.workflow_id}
      workflowExecutionId={params.workflow_execution_id}
    />
  );
}

export const metadata: Metadata = {
  title: "Keep - Workflow Execution Results",
};
