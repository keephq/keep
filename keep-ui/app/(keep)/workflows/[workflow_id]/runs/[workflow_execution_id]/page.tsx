"use client";
import React from "react";
import WorkflowExecutionResults from "@/app/(keep)/workflows/builder/workflow-execution-results";

export default function WorkflowExecutionPage({
  params,
}: {
  params: { workflow_id: string; workflow_execution_id: string };
}) {
  return (
    <WorkflowExecutionResults
      workflow_id={params.workflow_id}
      workflow_execution_id={params.workflow_execution_id}
    />
  );
}
