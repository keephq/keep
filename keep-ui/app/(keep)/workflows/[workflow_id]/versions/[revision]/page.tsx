"use client";

import { useParams } from "next/navigation";
import { useWorkflowDetail } from "@/entities/workflows/model";
import { WorkflowYAMLEditor } from "@/shared/ui";
import { Card } from "@tremor/react";

export default function WorkflowVersionPage() {
  const { workflow_id, revision } = useParams();

  const { workflow } = useWorkflowDetail(
    workflow_id as string,
    Number(revision)
  );

  return (
    <div className="flex flex-col gap-4">
      <h1>Workflow Revision {revision}</h1>
      <Card className="h-[calc(100vh-12rem)] p-0">
        <WorkflowYAMLEditor
          workflowYamlString={workflow?.workflow_raw ?? ""}
          readOnly={true}
        />
      </Card>
    </div>
  );
}
