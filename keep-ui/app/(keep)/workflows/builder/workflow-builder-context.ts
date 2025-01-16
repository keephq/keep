import { createContext, useContext } from "react";

interface WorkflowBuilderContextType {
  enableButtons: (state: boolean) => void;
  enableGenerate: (state: boolean) => void;
  triggerGenerate: number;
  triggerSave: number;
  triggerRun: number;
  setIsSaving: (state: boolean) => void;
  isSaving: boolean;
}

export const WorkflowBuilderContext = createContext<WorkflowBuilderContextType>(
  {
    enableButtons: (state: boolean) => {},
    enableGenerate: (state: boolean) => {},
    triggerGenerate: 0,
    triggerSave: 0,
    triggerRun: 0,
    setIsSaving: (state: boolean) => {},
    isSaving: false,
  }
);

export function useWorkflowBuilderContext() {
  const context = useContext(WorkflowBuilderContext);
  if (context === undefined) {
    throw new Error(
      "useWorkflowBuilderContext must be used within a WorkflowBuilderProvider"
    );
  }
  return context;
}
