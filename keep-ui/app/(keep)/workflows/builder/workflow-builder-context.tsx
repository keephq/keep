"use client";

import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
import { showErrorToast } from "@/shared/ui";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { ReactFlowDefinition, useStore, V2Step } from "./builder-store";
import { toast } from "react-toastify";
import { useRouter } from "next/navigation";
import {
  DefinitionV2,
  getDefinitionFromNodesEdgesProperties,
  wrapDefinitionV2,
} from "./utils";
import { debounce } from "lodash";
import { Definition, ValidatorConfigurationV2 } from "./types";
import { globalValidatorV2, stepValidatorV2 } from "./builder-validators";

const INITIAL_DEFINITION = wrapDefinitionV2({
  sequence: [],
  properties: {},
  isValid: false,
});

// TODO: move to builder store or somehow merge with it, so there's only one source of truth
interface WorkflowBuilderContextType {
  definition: DefinitionV2;
  validatorConfigurationV2: ValidatorConfigurationV2;
  stepValidationError: string | null;
  globalValidationError: string | null;
  generateEnabled: boolean;
  buttonsEnabled: boolean;
  generateRequestCount: number;
  saveRequestCount: number;
  runRequestCount: number;
  setDefinition: (definition: DefinitionV2) => void;
  triggerGenerate: () => void;
  triggerSave: () => void;
  triggerRun: () => void;
  enableButtons: (state: boolean) => void;
  setIsSaving: (state: boolean) => void;
  isSaving: boolean;
  workflowId: string;
  validationErrors: { step: string | null; global: string | null };
  setValidationErrors: (errors: {
    step: string | null;
    global: string | null;
  }) => void;
}

export const WorkflowBuilderContext = createContext<WorkflowBuilderContextType>(
  {
    definition: INITIAL_DEFINITION,
    stepValidationError: null,
    globalValidationError: null,
    validatorConfigurationV2: {
      step: (step: V2Step, parent?: V2Step, definition?: ReactFlowDefinition) =>
        false,
      root: (def: Definition) => false,
    },
    generateEnabled: false,
    buttonsEnabled: false,
    generateRequestCount: 0,
    saveRequestCount: 0,
    runRequestCount: 0,
    isSaving: false,
    setDefinition: () => {},
    triggerGenerate: () => {},
    triggerSave: () => {},
    triggerRun: () => {},
    enableButtons: (state: boolean) => {},
    setIsSaving: (state: boolean) => {},
    workflowId: "",
    validationErrors: { step: null, global: null },
    setValidationErrors: () => {},
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

export function WorkflowBuilderProvider({
  workflowId,
  children,
}: {
  workflowId: string;
  children: React.ReactNode;
}) {
  // Keep minimal UI state here
  const [validationErrors, setValidationErrors] = useState({
    step: null,
    global: null,
  });

  const value = {
    workflowId,
    validationErrors,
    setValidationErrors,
  };

  return (
    <WorkflowBuilderContext.Provider value={value}>
      {children}
    </WorkflowBuilderContext.Provider>
  );
}
