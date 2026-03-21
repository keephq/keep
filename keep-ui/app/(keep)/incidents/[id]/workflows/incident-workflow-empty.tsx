import { useState } from "react";
import { ManualRunWorkflowModal } from "@/features/workflows/manual-run-workflow";
import type { IncidentDto } from "@/entities/incidents/model";
import { EmptyStateCard } from "@/shared/ui";
import { Button } from "@tremor/react";
import { Workflows as WorkflowsIcon } from "components/icons";
import { useTranslations } from "next-intl";

export function IncidentWorkflowsEmptyState({
  incident,
}: {
  incident: IncidentDto;
}) {
  const t = useTranslations("incidents");
  const [runWorkflowModalIncident, setRunWorkflowModalIncident] =
    useState<IncidentDto | null>();

  const handleRunWorkflow = () => {
    setRunWorkflowModalIncident(incident);
  };

  return (
    <>
      <EmptyStateCard
        icon={() => <WorkflowsIcon className="!size-8" />}
        title={t("messages.noWorkflows")}
        description={t("messages.noWorkflowsDescription")}
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
          {t("actions.runAWorkflow")}
        </Button>
      </EmptyStateCard>

      <ManualRunWorkflowModal
        incident={runWorkflowModalIncident}
        onClose={() => setRunWorkflowModalIncident(null)}
      />
    </>
  );
}
