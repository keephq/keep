import { useWorkflowStore } from "@/entities/workflows";
import { Switch } from "@tremor/react";
import { showErrorToast } from "@/shared/ui";
import { useI18n } from "@/i18n/hooks/useI18n";

export function WorkflowEnabledSwitch() {
  const { updateV2Properties, triggerSave } = useWorkflowStore();
  const isValid = useWorkflowStore((state) => !!state.definition?.isValid);
  const isInitialized = useWorkflowStore((state) => !!state.workflowId);
  const isEnabled = useWorkflowStore(
    (state) => !!state.workflowId && !state.v2Properties?.disabled
  );
  const { t } = useI18n();
  let tooltip = undefined;
  if (!isValid) {
    tooltip = t("workflows.builder.fixErrorsBeforeEnabling");
  } else if (!isInitialized) {
    tooltip = t("workflows.builder.deployBeforeEnabling");
  } else if (isEnabled) {
    tooltip = t("workflows.builder.workflowEnabled");
  } else {
    tooltip = t("workflows.builder.workflowDisabled");
  }
  return (
    <div className="flex items-center gap-2 px-2">
      <Switch
        id="workflow-enabled-switch"
        checked={isEnabled}
        onChange={(flag) => {
          if (!isValid) {
            showErrorToast(
              new Error(t("workflows.builder.fixErrorsBeforeEnabling"))
            );
            return;
          }
          updateV2Properties({
            disabled: !flag,
          });
          triggerSave();
        }}
        tooltip={tooltip}
        disabled={!isValid}
      />
      <label className="text-sm" htmlFor="workflow-enabled-switch">
        {isEnabled ? t("common.labels.enabled") : t("common.labels.disabled")}
      </label>
    </div>
  );
}
