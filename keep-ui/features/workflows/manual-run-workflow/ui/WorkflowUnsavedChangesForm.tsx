import { useUIBuilderUnsavedChanges } from "@/entities/workflows/model/workflow-store";
import { useWorkflowYAMLEditorStore } from "@/entities/workflows/model/workflow-yaml-editor-store";
import { Button } from "@tremor/react";
import { useI18n } from "@/i18n/hooks/useI18n";

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
  const { t } = useI18n();
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
          {t("workflows.unsavedChanges.bothUnsaved")}
        </p>
        <div className="flex justify-between gap-2">
          <Button
            variant="secondary"
            size="sm"
            color="rose"
            onClick={onRunWithoutSaving}
          >
            {t("workflows.unsavedChanges.discardAllAndRun")}
          </Button>
          <Button variant="primary" size="sm" color="orange" type="submit">
            {t("workflows.unsavedChanges.returnToEditor")}
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
          {t("workflows.unsavedChanges.yamlUnsaved")}
        </p>
        <div className="flex justify-between gap-2">
          <Button
            variant="secondary"
            size="sm"
            color="orange"
            onClick={onClose}
          >
            {t("common.actions.cancel")}
          </Button>
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              size="sm"
              color="rose"
              onClick={onRunWithoutSaving}
              data-testid="wf-unsaved-changes-discard-and-run"
            >
              {t("workflows.unsavedChanges.discardAndRun")}
            </Button>
            <Button
              variant="primary"
              size="sm"
              color="orange"
              type="submit"
              data-testid="wf-unsaved-changes-save-and-run"
            >
              {t("workflows.unsavedChanges.saveAndRun")}
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
          {t("workflows.unsavedChanges.uiBuilderUnsaved")}
        </p>
        <div className="flex justify-between gap-2">
          <Button
            variant="secondary"
            size="sm"
            color="orange"
            onClick={onClose}
          >
            {t("common.actions.cancel")}
          </Button>
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              size="sm"
              color="orange"
              onClick={onRunWithoutSaving}
              data-testid="wf-unsaved-changes-discard-and-run"
            >
              {t("workflows.unsavedChanges.discardAndRun")}
            </Button>
            <Button
              variant="primary"
              size="sm"
              color="orange"
              type="submit"
              data-testid="wf-unsaved-changes-save-and-run"
            >
              {t("workflows.unsavedChanges.saveAndRun")}
            </Button>
          </div>
        </div>
      </form>
    );
  }
  // should not happen
  return t("common.actions.saving");
}
