"use client";

import { Button } from "@tremor/react";

// Import Button Component
export function ImportButton({ workflowId }: { workflowId: string }) {
  return (
    <Button
      size="lg"
      color="orange"
      onClick={() => {
        // Store the workflow ID
        localStorage.setItem("import_workflow_id", workflowId);
        // Redirect to login
        window.location.href = `/login?returnTo=/workflows/preview/${workflowId}`;
      }}
    >
      Import Workflow
    </Button>
  );
}
