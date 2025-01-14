import { useEffect, useMemo, useState } from "react";
import { Callout, Card } from "@tremor/react";
import { Provider } from "../../providers/providers";
import {
  parseWorkflow,
  generateWorkflow,
  getToolboxConfiguration,
  getWorkflowFromDefinition,
  wrapDefinitionV2,
} from "./utils";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/20/solid";
import { globalValidatorV2, stepValidatorV2 } from "./builder-validators";
import { LegacyWorkflow } from "./legacy-workflow.types";
import BuilderModalContent from "./builder-modal";
import Loader from "./loader";
import { stringify } from "yaml";
import { useRouter, useSearchParams } from "next/navigation";
import { v4 as uuidv4 } from "uuid";
import BuilderWorkflowTestRunModalContent from "./builder-workflow-testrun-modal";
import {
  Definition as FlowDefinition,
  ReactFlowDefinition,
  V2Step,
} from "./types";
import {
  WorkflowExecutionDetail,
  WorkflowExecutionFailure,
} from "@/shared/api/workflow-executions";
import ReactFlowBuilder from "./ReactFlowBuilder";
import { ReactFlowProvider } from "@xyflow/react";
import useStore from "./builder-store";
import { toast } from "react-toastify";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/api";
import { showErrorToast } from "@/shared/ui";
import { YAMLException } from "js-yaml";
import Modal from "@/components/ui/Modal";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
import debounce from "lodash.debounce";

interface Props {
  loadedAlertFile: string | null;
  fileName: string;
  providers: Provider[];
  enableGenerate: (status: boolean) => void;
  triggerGenerate: number;
  triggerSave: number;
  triggerRun: number;
  workflow?: string;
  workflowId?: string;
  installedProviders?: Provider[] | undefined | null;
  isPreview?: boolean;
}

const INITIAL_DEFINITION = wrapDefinitionV2({
  sequence: [],
  properties: {},
  isValid: false,
});

function Builder({
  loadedAlertFile,
  fileName,
  providers,
  enableGenerate,
  triggerGenerate,
  triggerSave,
  triggerRun,
  workflow,
  workflowId,
  installedProviders,
  isPreview,
}: Props) {
  const api = useApi();
  const [definition, setDefinition] = useState(INITIAL_DEFINITION);
  const [isLoading, setIsLoading] = useState(true);
  const [stepValidationError, setStepValidationError] = useState<string | null>(
    null
  );
  const [globalValidationError, setGlobalValidationError] = useState<
    string | null
  >(null);
  const [generateModalIsOpen, setGenerateModalIsOpen] = useState(false);
  const [testRunModalOpen, setTestRunModalOpen] = useState(false);
  const [runningWorkflowExecution, setRunningWorkflowExecution] = useState<
    WorkflowExecutionDetail | WorkflowExecutionFailure | null
  >(null);
  const [legacyWorkflow, setLegacyWorkflow] = useState<LegacyWorkflow | null>(
    null
  );
  const router = useRouter();

  const searchParams = useSearchParams();
  const { errorNode, setErrorNode, canDeploy, synced, reset } = useStore();

  const setStepValidationErrorV2 = (step: V2Step, error: string | null) => {
    setStepValidationError(error);
    if (error && step) {
      return setErrorNode(step.id);
    }
    setErrorNode(null);
  };

  const setGlobalValidationErrorV2 = (
    id: string | null,
    error: string | null
  ) => {
    setGlobalValidationError(error);
    if (error && id) {
      return setErrorNode(id);
    }
    setErrorNode(null);
  };

  const testRunWorkflow = () => {
    setTestRunModalOpen(true);
    const body = stringify(getWorkflowFromDefinition(definition.value));
    api
      .request(`/workflows/test`, {
        method: "POST",
        body,
        headers: { "Content-Type": "text/html" },
      })
      .then((data) => {
        setRunningWorkflowExecution({
          ...data,
        });
      })
      .catch((error) => {
        setRunningWorkflowExecution({
          error:
            error instanceof KeepApiError ? error.message : "Unknown error",
        });
      });
  };

  const { createWorkflow, updateWorkflow } = useWorkflowActions();

  const addWorkflowDebounced = useMemo(
    () =>
      debounce(async () => {
        try {
          const response = await createWorkflow(definition.value);
          // reset the store to clear the nodes and edges
          if (response?.workflow_id) {
            router.push(`/workflows/${response.workflow_id}`);
          }
        } catch (error) {
          // error is handled in the useWorkflowActions hook
          console.error(error);
        }
      }, 1000),
    [createWorkflow, definition.value, router]
  );

  const updateWorkflowDebounced = useMemo(
    () =>
      debounce(() => {
        if (workflowId) {
          updateWorkflow(workflowId, definition.value);
        }
      }, 1000),
    [updateWorkflow, workflowId, definition.value]
  );

  useEffect(
    function updateDefinitionFromInput() {
      setIsLoading(true);
      try {
        if (workflow) {
          setDefinition(
            wrapDefinitionV2({
              ...parseWorkflow(workflow, providers),
              isValid: true,
            })
          );
        } else if (loadedAlertFile == null) {
          const alertUuid = uuidv4();
          const alertName = searchParams?.get("alertName");
          const alertSource = searchParams?.get("alertSource");
          let triggers = {};
          if (alertName && alertSource) {
            triggers = { alert: { source: alertSource, name: alertName } };
          }
          setDefinition(
            wrapDefinitionV2({
              ...generateWorkflow(
                alertUuid,
                "",
                "",
                false,
                {},
                [],
                [],
                triggers
              ),
              isValid: true,
            })
          );
        } else {
          const parsedDefinition = parseWorkflow(loadedAlertFile!, providers);
          setDefinition(
            wrapDefinitionV2({
              ...parsedDefinition,
              isValid: true,
            })
          );
        }
      } catch (error) {
        if (error instanceof YAMLException) {
          showErrorToast(error, "Invalid YAML: " + error.message);
        } else {
          showErrorToast(error, "Failed to load workflow");
        }
      }
      setIsLoading(false);
    },
    [loadedAlertFile, workflow, searchParams, providers]
  );

  useEffect(() => {
    if (triggerGenerate) {
      setLegacyWorkflow(getWorkflowFromDefinition(definition.value));
      if (!generateModalIsOpen) setGenerateModalIsOpen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggerGenerate]);

  useEffect(() => {
    if (triggerRun) {
      testRunWorkflow();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggerRun]);

  const hasErrors = errorNode || !definition.isValid;

  useEffect(() => {
    if (!triggerSave && !canDeploy) {
      return;
    }
    if (!synced) {
      toast(
        "Please save the previous step or wait while properties sync with the workflow."
      );
      return;
    }
    if (hasErrors) {
      showErrorToast("Please fix the errors in the workflow before saving.");
      return;
    }
    if (workflowId) {
      updateWorkflowDebounced();
    } else {
      addWorkflowDebounced();
    }
  }, [
    addWorkflowDebounced,
    updateWorkflowDebounced,
    synced,
    triggerSave,
    workflowId,
    hasErrors,
    canDeploy,
  ]);

  useEffect(
    function resetZustandStateOnUnMount() {
      return () => {
        reset();
      };
    },
    [reset]
  );

  useEffect(() => {
    enableGenerate(
      (definition.isValid &&
        stepValidationError === null &&
        globalValidationError === null) ||
        false
    );
  }, [
    stepValidationError,
    globalValidationError,
    enableGenerate,
    definition.isValid,
  ]);

  if (isLoading) {
    return (
      <Card className={`p-4 md:p-10 mx-auto max-w-7xl mt-6`}>
        <Loader />
      </Card>
    );
  }

  const ValidatorConfigurationV2: {
    step: (
      step: V2Step,
      parent?: V2Step,
      definition?: ReactFlowDefinition
    ) => boolean;
    root: (def: FlowDefinition) => boolean;
  } = {
    step: (step, parent, definition) =>
      stepValidatorV2(step, setStepValidationErrorV2, parent, definition),
    root: (def) => globalValidatorV2(def, setGlobalValidationErrorV2),
  };

  function closeGenerateModal() {
    setGenerateModalIsOpen(false);
  }

  const closeWorkflowExecutionResultsModal = () => {
    setTestRunModalOpen(false);
    setRunningWorkflowExecution(null);
  };

  const getworkflowStatus = () => {
    return stepValidationError || globalValidationError ? (
      <Callout
        className="mt-2.5 mb-2.5"
        title="Validation Error"
        icon={ExclamationCircleIcon}
        color="rose"
      >
        {stepValidationError || globalValidationError}
      </Callout>
    ) : (
      <Callout
        className="mt-2.5 mb-2.5"
        title="Schema Valid"
        icon={CheckCircleIcon}
        color="teal"
      >
        Workflow can be generated successfully
      </Callout>
    );
  };

  return (
    <div className="h-full">
      <Modal
        onClose={closeGenerateModal}
        isOpen={generateModalIsOpen}
        className="bg-gray-50 p-4 md:p-10 mx-auto max-w-7xl mt-20 border border-orange-600/50 rounded-md"
      >
        <BuilderModalContent
          closeModal={closeGenerateModal}
          compiledAlert={legacyWorkflow}
        />
      </Modal>
      <Modal
        isOpen={testRunModalOpen}
        onClose={closeWorkflowExecutionResultsModal}
        className="bg-gray-50 p-4 md:p-10 mx-auto max-w-7xl mt-20 border border-orange-600/50 rounded-md"
      >
        <BuilderWorkflowTestRunModalContent
          closeModal={closeWorkflowExecutionResultsModal}
          workflowExecution={runningWorkflowExecution}
          workflowRaw={workflow ?? ""}
          workflowId={workflowId ?? ""}
        />
      </Modal>
      {generateModalIsOpen || testRunModalOpen ? null : (
        <>
          {getworkflowStatus()}
          <Card className="mt-2 p-0 h-[90%] overflow-hidden">
            <div className="flex h-full">
              <div className="flex-1 h-full relative">
                <ReactFlowProvider>
                  <ReactFlowBuilder
                    providers={providers}
                    installedProviders={installedProviders}
                    definition={definition}
                    validatorConfiguration={ValidatorConfigurationV2}
                    onDefinitionChange={(def: any) => {
                      setDefinition({
                        value: {
                          sequence: def?.sequence || [],
                          properties: def?.properties || {},
                        },
                        isValid: def?.isValid || false,
                      });
                    }}
                    toolboxConfiguration={getToolboxConfiguration(providers)}
                  />
                </ReactFlowProvider>
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

export default Builder;
