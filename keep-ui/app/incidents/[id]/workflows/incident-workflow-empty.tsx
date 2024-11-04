import { useState } from "react";
import { EmptyStateCard } from "@/components/ui";
import ManualRunWorkflowModal from "@/app/workflows/manual-run-workflow-modal";
import { IncidentDto } from "../../models";

export function IncidentWorkflowsEmptyState({
  incident,
}: {
  incident: IncidentDto;
}) {
  const [runWorkflowModalIncident, setRunWorkflowModalIncident] =
    useState<IncidentDto | null>();

  const handleRunWorkflow = () => {
    console.log("handleRunWorkflow", incident);
    setRunWorkflowModalIncident(incident);
  };

  return (
    <>
      <EmptyStateCard
        title="No Workflows"
        description="No workflows have been executed for this incident yet."
        buttonText="Run a workflow"
        onClick={(e) => {
          console.log("'Run a workflow' clicked");
          e.preventDefault();
          e.stopPropagation();
          handleRunWorkflow();
        }}
      />
      <ManualRunWorkflowModal
        incident={runWorkflowModalIncident}
        handleClose={() => setRunWorkflowModalIncident(null)}
      />
    </>
  );
}
