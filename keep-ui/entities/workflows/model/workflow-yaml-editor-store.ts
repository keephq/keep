import { YamlValidationError } from "@/shared/ui/WorkflowYAMLEditor/model/types";
import { create } from "zustand";
import { devtools } from "zustand/middleware";

type WorkflowYAMLEditorStateValues = {
  workflowId: string | null;
  hasUnsavedChanges: boolean;
  validationErrors: YamlValidationError[];
};

const defaultState: WorkflowYAMLEditorStateValues = {
  workflowId: null,
  hasUnsavedChanges: false,
  validationErrors: [],
};

type WorkflowYAMLEditorState = WorkflowYAMLEditorStateValues & {
  setWorkflowId: (workflowId: string | null) => void;
  setHasUnsavedChanges: (hasUnsavedChanges: boolean) => void;
  setValidationErrors: (validationErrors: YamlValidationError[]) => void;
};

export const useWorkflowYAMLEditorStore = create<WorkflowYAMLEditorState>()(
  devtools((set, get) => ({
    ...defaultState,
    setWorkflowId: (workflowId: string | null) => set({ workflowId }),
    setHasUnsavedChanges: (hasUnsavedChanges: boolean) =>
      set({ hasUnsavedChanges }),
    setValidationErrors: (validationErrors: YamlValidationError[]) =>
      set({ validationErrors }),
  }))
);
