import { createContext, useContext } from "react";

interface WorkflowBuilderContextType {
  generateRequestCount: number;
  saveRequestCount: number;
  runRequestCount: number;
  triggerGenerate: () => void;
  triggerSave: () => void;
  triggerRun: () => void;
  enableButtons: (state: boolean) => void;
  enableGenerate: (state: boolean) => void;
  setIsSaving: (state: boolean) => void;
  isSaving: boolean;
}

export const WorkflowBuilderContext = createContext<WorkflowBuilderContextType>(
  {
    generateRequestCount: 0,
    triggerGenerate: () => {},
    saveRequestCount: 0,
    triggerSave: () => {},
    runRequestCount: 0,
    triggerRun: () => {},
    enableButtons: (state: boolean) => {},
    enableGenerate: (state: boolean) => {},
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
