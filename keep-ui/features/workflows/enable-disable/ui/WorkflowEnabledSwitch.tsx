import { useWorkflowStore } from "@/entities/workflows";
import { Switch } from "@tremor/react";
import { showErrorToast } from "@/shared/ui";

export function WorkflowEnabledSwitch() {
  const { updateV2Properties, triggerSave } = useWorkflowStore();
  const isValid = useWorkflowStore((state) => !!state.definition?.isValid);
  const isInitialized = useWorkflowStore((state) => !!state.workflowId);
  const isEnabled = useWorkflowStore(
    (state) => !!state.workflowId && !state.v2Properties?.disabled
  );
  let tooltip = undefined;
  if (!isValid) {
    tooltip = "Fix the errors in the workflow before enabling it";
  } else if (!isInitialized) {
    tooltip = "Deploy the workflow before enabling it";
  } else if (isEnabled) {
    tooltip = "The workflow is enabled";
  } else {
    tooltip = "The workflow is disabled";
  }
  return (
    <div className="flex items-center gap-2 px-2">
      <Switch
        id="workflow-enabled-switch"
        checked={isEnabled}
        onChange={(flag) => {
          if (!isValid) {
            showErrorToast(
              new Error("Fix the errors in the workflow before enabling it")
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
        {isEnabled ? "Enabled" : "Disabled"}
      </label>
    </div>
  );
}
