import { useState } from "react";
import ManualRunWorkflowModal from "@/app/(keep)/workflows/manual-run-workflow-modal";
import type { IncidentDto } from "@/entities/incidents/model";
import { EmptyStateCard } from "@/shared/ui";
import { Button } from "@tremor/react";
import { Workflows as WorkflowsIcon } from "components/icons";
export function IncidentWorkflowsEmptyState({
  incident,
}: {
  incident: IncidentDto;
}) {
  const [runWorkflowModalIncident, setRunWorkflowModalIncident] =
    useState<IncidentDto | null>();

  const handleRunWorkflow = () => {
    setRunWorkflowModalIncident(incident);
  };

  return (
    <>
      <EmptyStateCard
        icon={() => <WorkflowsIcon className="!size-8" />}
        title="No Workflows"
        description="No workflows have been executed for this incident yet."
      >
        <Button
          color="orange"
          variant="primary"
          size="md"
          onClick={(e) => {
            console.log("'Run a workflow' clicked");
            e.preventDefault();
            e.stopPropagation();
            handleRunWorkflow();
          }}
        >
          Run a workflow
        </Button>
      </EmptyStateCard>

      <ManualRunWorkflowModal
        incident={runWorkflowModalIncident}
        handleClose={() => setRunWorkflowModalIncident(null)}
      />
    </>
  );
}
