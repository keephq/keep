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
  const [buttonsEnabled, setButtonsEnabled] = useState(false);
  // signals for saving, generating, running the workflow
  const [generateRequestCount, setGenerateRequestCount] = useState(0);
  const [saveRequestCount, setSaveRequestCount] = useState(0);
  const [runRequestCount, setRunRequestCount] = useState(0);
  const [isSaving, setIsSaving] = useState(false);

  const [stepValidationError, setStepValidationError] = useState<string | null>(
    null
  );
  const [globalValidationError, setGlobalValidationError] = useState<
    string | null
  >(null);

  const enableButtons = (state: boolean) => setButtonsEnabled(state);
  const incrementState = (s: number) => s + 1;
  const triggerSave = () => setSaveRequestCount(incrementState);
  const triggerGenerate = () => setGenerateRequestCount(incrementState);
  const triggerRun = () => setRunRequestCount(incrementState);

  const [definition, setDefinition] = useState(INITIAL_DEFINITION);

  const router = useRouter();

  const { createWorkflow, updateWorkflow } = useWorkflowActions();
  const {
    errorNode,
    setErrorNode,
    synced,
    reset,
    canDeploy,
    v2Properties,
    updateV2Properties,
    nodes,
    edges,
    setSynced,
    changes,
  } = useStore();

  const setStepValidationErrorV2 = useCallback(
    (step: V2Step, error: string | null) => {
      setStepValidationError(error);
      if (error && step) {
        return setErrorNode(step.id);
      }
      setErrorNode(null);
    },
    [setStepValidationError, setErrorNode]
  );

  const setGlobalValidationErrorV2 = useCallback(
    (id: string | null, error: string | null) => {
      setGlobalValidationError(error);
      if (error && id) {
        return setErrorNode(id);
      }
      setErrorNode(null);
    },
    [setGlobalValidationError, setErrorNode]
  );

  const validatorConfigurationV2: {
    step: (
      step: V2Step,
      parent?: V2Step,
      definition?: ReactFlowDefinition
    ) => boolean;
    root: (def: Definition) => boolean;
  } = useMemo(() => {
    return {
      step: (step, parent, definition) =>
        stepValidatorV2(step, setStepValidationErrorV2, parent, definition),
      root: (def) => globalValidatorV2(def, setGlobalValidationErrorV2),
    };
  }, [setStepValidationErrorV2, setGlobalValidationErrorV2]);

  // todo: sync v2Properties with definition
  useEffect(() => {
    setSynced(false);

    const handleDefinitionChange = () => {
      const newDefinition = getDefinitionFromNodesEdgesProperties(
        nodes,
        edges,
        v2Properties,
        validatorConfigurationV2
      );
      setDefinition(wrapDefinitionV2(newDefinition));
      setSynced(true);
    };
    const debouncedHandleDefinitionChange = debounce(
      handleDefinitionChange,
      300
    );

    debouncedHandleDefinitionChange();

    return () => {
      debouncedHandleDefinitionChange.cancel();
    };
  }, [changes]);

  // save workflow on "Deploy" button click
  useEffect(() => {
    if (saveRequestCount) {
      saveWorkflow(definition);
    }
    // ignore since we want the latest values, but to run effect only when triggerSave changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saveRequestCount]);

  // save workflow on "Save & Deploy" button click from FlowEditor
  useEffect(() => {
    if (canDeploy) {
      saveWorkflow(definition);
    }
    // ignore since we want the latest values, but to run effect only when triggerSave changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canDeploy]);

  const saveWorkflow = useCallback(
    async (definition: DefinitionV2, forceSave: boolean = false) => {
      if (!synced && !forceSave) {
        toast(
          "Please save the previous step or wait while properties sync with the workflow."
        );
        return;
      }
      if (errorNode || !definition.isValid) {
        showErrorToast("Please fix the errors in the workflow before saving.");
        return;
      }
      try {
        setIsSaving(true);
        if (workflowId) {
          await updateWorkflow(workflowId, definition.value);
        } else {
          const response = await createWorkflow(definition.value);
          if (response?.workflow_id) {
            router.push(`/workflows/${response.workflow_id}`);
          }
        }
      } catch (error) {
        console.error(error);
      } finally {
        setIsSaving(false);
      }
    },
    [
      synced,
      errorNode,
      setIsSaving,
      workflowId,
      updateWorkflow,
      createWorkflow,
      router,
    ]
  );

  useEffect(
    function resetZustandStateOnUnMount() {
      return () => {
        reset();
      };
    },
    [reset]
  );

  const generateEnabled = useMemo(() => {
    return (
      definition.isValid &&
      stepValidationError === null &&
      globalValidationError === null
    );
  }, [definition.isValid, stepValidationError, globalValidationError]);

  return (
    <WorkflowBuilderContext.Provider
      value={{
        definition,
        validatorConfigurationV2,

        stepValidationError,
        globalValidationError,

        generateEnabled,
        buttonsEnabled,
        generateRequestCount,
        saveRequestCount,
        runRequestCount,
        setDefinition,
        triggerGenerate,
        triggerSave,
        triggerRun,
        enableButtons,
        setIsSaving,
        isSaving,
      }}
    >
      {children}
    </WorkflowBuilderContext.Provider>
  );
}
