import {
  useWorkflowDetail,
  useWorkflowRevisions,
} from "@/entities/workflows/model";
import { Card, Text } from "@tremor/react";
import { format } from "date-fns";
import { KeepLoader, WorkflowYAMLEditor } from "@/shared/ui";
import { useState } from "react";

export function WorkflowRevisions({
  workflowId,
  currentRevision,
}: {
  workflowId: string;
  currentRevision: number | null;
}) {
  const [selectedRevision, setSelectedRevision] = useState<number | null>(
    currentRevision
  );
  const { data, isLoading, error } = useWorkflowRevisions(workflowId);
  const { workflow } = useWorkflowDetail(workflowId, selectedRevision);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-48">
        <KeepLoader
          includeMinHeight={false}
          loadingText="Loading workflow revisions"
        />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <Text color="red">Error loading workflow revisions</Text>
      </div>
    );
  }

  if (!data || data.versions.length === 0) {
    return (
      <div className="p-4">
        <Text>No revisions found for this workflow</Text>
      </div>
    );
  }

  return (
    <Card className="h-[calc(100vh-12rem)] flex p-0">
      <div className="flex-1 p-[2px] h-full min-w-0 border-r border-gray-200">
        <WorkflowYAMLEditor
          filename={
            workflow?.name.replaceAll(" ", "_") +
            "_v" +
            workflow?.revision +
            ".yaml"
          }
          workflowYamlString={workflow?.workflow_raw ?? ""}
          readOnly={true}
        />
      </div>
      <div className="flex flex-col basis-1/4 min-w-0">
        {data.versions.map((revision) => (
          <button
            key={revision.revision}
            className={`flex flex-col border-b border-gray-200 p-2 text-left ${
              selectedRevision === revision.revision
                ? "bg-orange-500 text-white"
                : " text-gray-800"
            }`}
            onClick={() => setSelectedRevision(revision.revision)}
          >
            <span className="text-sm font-bold">
              Revision {revision.revision}{" "}
              {currentRevision === revision.revision ? "(Current)" : ""}
            </span>
            <span className="text-xs">
              {format(new Date(revision.last_updated), "MMM d, yyyy HH:mm:ss")}
            </span>
            <span className="text-xs">{revision.updated_by}</span>
          </button>
        ))}
      </div>
    </Card>
  );
}
