"use client";
import { useI18n } from "@/i18n/hooks/useI18n";

import { useParams } from "next/navigation";
import { useWorkflowDetail } from "@/entities/workflows/model";
import { WorkflowYAMLEditor } from "@/shared/ui";
import { Card } from "@tremor/react";

export default function WorkflowVersionPage() {
  const { t } = useI18n();
  const { workflow_id, revision } = useParams();

  const { workflow } = useWorkflowDetail(
    workflow_id as string,
    Number(revision)
  );

  return (
    <div className="flex flex-col gap-4">
      <h1>{t("workflows.breadcrumbs.workflowRevision", { revision })}</h1>
      <Card className="h-[calc(100vh-12rem)] p-0">
        <WorkflowYAMLEditor
          value={workflow?.workflow_raw ?? ""}
          readOnly={true}
        />
      </Card>
    </div>
  );
}
