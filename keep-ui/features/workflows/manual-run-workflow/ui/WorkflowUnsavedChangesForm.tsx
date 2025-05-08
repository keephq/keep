import { useUIBuilderUnsavedChanges } from "@/entities/workflows/model/workflow-store";
import { useWorkflowYAMLEditorStore } from "@/entities/workflows/model/workflow-yaml-editor-store";
import { Button } from "@tremor/react";

export function WorkflowUnsavedChangesForm({
  onClose,
  onSaveYaml,
  onSaveUIBuilder,
  onRunWithoutSaving,
}: {
  onClose: () => void;
  onSaveYaml: () => void;
  onSaveUIBuilder: () => void;
  onRunWithoutSaving: () => void;
}) {
  const isUIBuilderUnsaved = useUIBuilderUnsavedChanges();
  const { hasUnsavedChanges: isYamlEditorUnsaved } =
    useWorkflowYAMLEditorStore();

  if (isYamlEditorUnsaved && isUIBuilderUnsaved) {
    return (
      <div className="flex flex-col gap-4">
        <p>
          You have unsaved changes in both the YAML editor and the workflow
          editor. Which one do you want to save?
        </p>
        <div className="flex justify-between gap-2">
          <Button
            variant="secondary"
            size="sm"
            color="orange"
            onClick={onClose}
          >
            Cancel
          </Button>
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              size="sm"
              color="rose"
              onClick={onClose}
            >
              Discard all changes and run
            </Button>
            <Button
              variant="primary"
              size="sm"
              color="orange"
              onClick={onClose}
            >
              Return to editor
            </Button>
          </div>
        </div>
      </div>
    );
  }
  if (isYamlEditorUnsaved) {
    return (
      <div className="flex flex-col gap-4">
        <p>
          You have unsaved changes in the YAML editor. Do you want to save them?
        </p>
        <div className="flex justify-between gap-2">
          <Button
            variant="secondary"
            size="sm"
            color="orange"
            onClick={onClose}
          >
            Cancel
          </Button>
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              size="sm"
              color="rose"
              onClick={onRunWithoutSaving}
            >
              Discard changes and run
            </Button>
            <Button
              variant="primary"
              size="sm"
              color="orange"
              onClick={onSaveYaml}
            >
              Save and run
            </Button>
          </div>
        </div>
      </div>
    );
  }
  if (isUIBuilderUnsaved) {
    return (
      <div className="flex flex-col gap-4">
        <p>
          You have unsaved changes in the workflow UI builder. Do you want to
          save them?
        </p>
        <div className="flex justify-between gap-2">
          <Button
            variant="secondary"
            size="sm"
            color="orange"
            onClick={onClose}
          >
            Cancel
          </Button>
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              size="sm"
              color="orange"
              onClick={onRunWithoutSaving}
            >
              Discard changes and run
            </Button>
            <Button
              variant="primary"
              size="sm"
              color="orange"
              onClick={onSaveUIBuilder}
            >
              Save and run
            </Button>
          </div>
        </div>
      </div>
    );
  }
  // should not happen
  return "Saving...";
}
