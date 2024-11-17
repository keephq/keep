"use client";
import React, { use } from "react";
import WorkflowExecutionResults from "app/workflows/builder/workflow-execution-results";

export default function WorkflowExecutionPage(
  props: {
    params: Promise<{ workflow_id: string; workflow_execution_id: string }>;
  }
) {
  const params = use(props.params);
  return (
    <WorkflowExecutionResults workflow_id={params.workflow_id} workflow_execution_id={params.workflow_execution_id} />
  );
}
