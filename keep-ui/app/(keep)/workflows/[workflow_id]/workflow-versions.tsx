import {
  useWorkflowDetail,
  useWorkflowRevisions,
} from "@/entities/workflows/model";
import { Badge, Card, Subtitle, Switch, Text } from "@tremor/react";
import { format } from "date-fns";
import { KeepLoader, WorkflowYAMLEditor } from "@/shared/ui";
import { useMemo, useState } from "react";
import { getOrderedWorkflowYamlString } from "@/entities/workflows/lib/yaml-utils";
import UserAvatar from "@/components/navbar/UserAvatar";
import clsx from "clsx";

export function WorkflowVersions({
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
    showDiff && previousRevision !== null ? workflowId : null,
    previousRevision
  );

  const uniqueYears = useMemo(() => {
    return [
      ...new Set(
        (data?.versions ?? []).map((revision) => {
          return format(new Date(revision.last_updated), "yyyy");
        })
      ),
    ];
  }, [data?.versions]);

  let formatString = "MMM d, yyyy HH:mm:ss";
  if (uniqueYears?.length === 1) {
    formatString = "MMM d, HH:mm:ss";
  }

  if (error) {
    return (
      <div className="p-4">
        <Text color="red">Error loading workflow revisions</Text>
      </div>
    );
  }

  if (data?.versions.length === 0) {
    return (
      <div className="p-4">
        <Text>No revisions found for this workflow</Text>
      </div>
    );
  }

  // showing loader if loading is not yet started to avoid flash of content
  if (isLoading || !data) {
    return (
      <div className="flex justify-center items-center h-48">
        <KeepLoader
          includeMinHeight={false}
          loadingText="Loading workflow revisions"
        />
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
          {data.versions.map((revision) => {
            let userName = revision.updated_by;
            if (!userName && revision.revision === 1) {
              userName = workflow?.created_by ?? "";
            }
            return (
              <button
                key={revision.revision}
                className={clsx(
                  "flex flex-col gap-1 border-b border-gray-200 p-2 text-left text-gray-800 text-sm",
                  selectedRevision === revision.revision
                    ? "bg-slate-200/70"
                    : "hover:bg-slate-50"
                )}
                onClick={() => setSelectedRevision(revision.revision)}
              >
                <span className="font-bold flex items-center gap-1 leading-none">
                  Revision {revision.revision}
                  {currentRevision === revision.revision ? (
                    <Badge color="green" size="xs" className="text-xs">
                      Current
                    </Badge>
                  ) : null}
                </span>
                <span>
                  {format(new Date(revision.last_updated), formatString)}
                </span>
                <span className="flex items-center gap-1">
                  <UserAvatar size="xs" image={null} name={userName ?? ""} />{" "}
                  <Subtitle className="truncate">{userName ?? ""}</Subtitle>
                </span>
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2 min-h-0 p-2 text-sm">
          <Switch
            id="show-diff"
            checked={showDiff}
            onChange={() => setShowDiff(!showDiff)}
          />
          <label htmlFor="show-diff">Show diff from previous revision</label>
        </div>
      </div>
    </Card>
  );
}
