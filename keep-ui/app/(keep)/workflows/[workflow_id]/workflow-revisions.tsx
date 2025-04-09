import {
  useWorkflowDetail,
  useWorkflowRevisions,
} from "@/entities/workflows/model";
import { Card, Switch, Text } from "@tremor/react";
import { format } from "date-fns";
import { KeepLoader, WorkflowYAMLEditor } from "@/shared/ui";
import { useMemo, useState } from "react";
import { getOrderedWorkflowYamlString } from "@/entities/workflows/lib/yaml-utils";

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
  const [showDiff, setShowDiff] = useState(true);
  const { data, isLoading, error } = useWorkflowRevisions(workflowId);
  const { workflow } = useWorkflowDetail(workflowId, selectedRevision);
  const previousRevision = useMemo(() => {
    if (!selectedRevision || !data?.versions.length) {
      return null;
    }
    const index = data.versions.findIndex(
      (v) => v.revision === selectedRevision
    );
    const previousIndex = index + 1; // +1 because they sorted descending
    if (previousIndex >= data.versions.length) {
      return null;
    }
    return data.versions[previousIndex]?.revision;
  }, [selectedRevision, data]);
  const { workflow: previousWorkflow } = useWorkflowDetail(
    previousRevision !== null && showDiff ? workflowId : null,
    previousRevision
  );

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

  const editorProps = previousWorkflow
    ? {
        original: getOrderedWorkflowYamlString(previousWorkflow.workflow_raw),
        modified: getOrderedWorkflowYamlString(workflow?.workflow_raw ?? ""),
      }
    : {
        value: getOrderedWorkflowYamlString(workflow?.workflow_raw ?? ""),
      };

  return (
    <Card className="h-[calc(100vh-12rem)] flex p-0 overflow-hidden relative">
      <div className="flex-1 p-[2px] h-full min-w-0 border-r border-gray-200">
        <WorkflowYAMLEditor
          filename={
            workflow?.name.replaceAll(" ", "_") +
            "_v" +
            workflow?.revision +
            ".yaml"
          }
          readOnly={true}
          {...editorProps}
        />
      </div>
      <div className="flex flex-col basis-1/4 min-w-0 justify-between">
        <div className="flex flex-col overflow-y-auto">
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
                {format(
                  new Date(revision.last_updated),
                  "MMM d, yyyy HH:mm:ss"
                )}
              </span>
              <span className="text-xs">{revision.updated_by}</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 min-h-0 p-2">
          <Switch
            id="show-diff"
            checked={showDiff}
            onChange={() => setShowDiff(!showDiff)}
          />
          <label htmlFor="show-diff">Show diff </label>
        </div>
      </div>
    </Card>
  );
}
