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
      <form
        className="flex flex-col gap-4"
        data-testid="wf-yaml-ui-unsaved-changes-form"
        onSubmit={(e) => {
          e.preventDefault();
          onClose();
        }}
      >
        <p>
          You have unsaved changes in both the YAML editor and the workflow
          editor. Please save your changes before running the workflow.
        </p>
        <div className="flex justify-between gap-2">
          <Button
            variant="secondary"
            size="sm"
            color="rose"
            onClick={onRunWithoutSaving}
          >
            Discard all changes and run
          </Button>
          <Button variant="primary" size="sm" color="orange" type="submit">
            Return to editor
          </Button>
        </div>
      </form>
    );
  }
  if (isYamlEditorUnsaved) {
    return (
      <form
        className="flex flex-col gap-4"
        data-testid="wf-yaml-unsaved-changes-form"
        onSubmit={(e) => {
          e.preventDefault();
          onSaveYaml();
        }}
      >
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
              data-testid="wf-unsaved-changes-discard-and-run"
            >
              Discard changes and run
            </Button>
            <Button
              variant="primary"
              size="sm"
              color="orange"
              type="submit"
              data-testid="wf-unsaved-changes-save-and-run"
            >
              Save and run
            </Button>
          </div>
        </div>
      </form>
    );
  }
  if (isUIBuilderUnsaved) {
    return (
      <form
        className="flex flex-col gap-4"
        data-testid="wf-ui-unsaved-changes-form"
        onSubmit={(e) => {
          e.preventDefault();
          onSaveUIBuilder();
        }}
      >
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
              data-testid="wf-unsaved-changes-discard-and-run"
            >
              Discard changes and run
            </Button>
            <Button
              variant="primary"
              size="sm"
              color="orange"
              type="submit"
              data-testid="wf-unsaved-changes-save-and-run"
            >
              Save and run
            </Button>
          </div>
        </div>
      </form>
    );
  }
  // should not happen
  return "Saving...";
}
