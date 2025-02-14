import { useCallback, useEffect, useMemo, useState } from "react";
import { Callout, Card } from "@tremor/react";
import { Provider } from "../../providers/providers";
import {
  parseWorkflow,
  generateWorkflow,
  getToolboxConfiguration,
  getWorkflowFromDefinition,
  wrapDefinitionV2,
  getDefinitionFromNodesEdgesProperties,
  DefinitionV2,
} from "./utils";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/20/solid";
import { globalValidatorV2, stepValidatorV2 } from "./builder-validators";
import { LegacyWorkflow } from "./legacy-workflow.types";
import BuilderModalContent from "./builder-modal";
import { EmptyBuilderState } from "./empty-builder-state";
import { stringify } from "yaml";
import { useRouter, useSearchParams } from "next/navigation";
import { v4 as uuidv4 } from "uuid";
import BuilderWorkflowTestRunModalContent from "./builder-workflow-testrun-modal";
import {
  Definition,
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
import { useStore } from "./builder-store";
import { toast } from "react-toastify";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/api";
import { showErrorToast } from "@/shared/ui";
import { YAMLException } from "js-yaml";
import { CopilotKit } from "@copilotkit/react-core";
import { BuilderChat } from "./builder-chat";
import Modal from "@/components/ui/Modal";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
import { useWorkflowBuilderContext } from "./workflow-builder-context";
import ResizableColumns from "@/components/ui/ResizableColumns";
import { EditWorkflowMetadataForm } from "@/features/edit-workflow-metadata";

interface Props {
  loadedAlertFile: string | null;
  fileName: string;
  providers: Provider[];
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
  const { createWorkflow, updateWorkflow } = useWorkflowActions();
  const {
    generateRequestCount,
    saveRequestCount,
    runRequestCount,
    enableGenerate,
    setIsSaving,
    triggerSave,
  } = useWorkflowBuilderContext();
  const router = useRouter();

  const searchParams = useSearchParams();
  const isEditModalOpen = searchParams.get("edit") === "true";
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
    if (generateRequestCount) {
      setLegacyWorkflow(getWorkflowFromDefinition(definition.value));
      if (!generateModalIsOpen) setGenerateModalIsOpen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [generateRequestCount]);

  useEffect(() => {
    if (runRequestCount) {
      testRunWorkflow();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runRequestCount]);

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

  const ValidatorConfigurationV2: {
    step: (
      step: V2Step,
      parent?: V2Step,
      definition?: ReactFlowDefinition
    ) => boolean;
    root: (def: FlowDefinition) => boolean;
  } = useMemo(() => {
    return {
      step: (step, parent, definition) =>
        stepValidatorV2(step, setStepValidationErrorV2, parent, definition),
      root: (def) => globalValidatorV2(def, setGlobalValidationErrorV2),
    };
  }, [setStepValidationErrorV2, setGlobalValidationErrorV2]);

  const setWrappedDefinition = useCallback(
    (def: Definition) => {
      setDefinition(wrapDefinitionV2(def));
    },
    [setDefinition]
  );

  // console.log("definition=", definition);
  console.log("nodes.length=", nodes.length);
  console.log("edges.length=", edges.length);

  const updateWorkflowMetadata = useCallback(
    (
      workflowId: string,
      { name, description }: { name: string; description: string }
    ) => {
      updateV2Properties({
        name,
        description,
      });
      const newDefinition = getDefinitionFromNodesEdgesProperties(
        nodes,
        edges,
        { ...v2Properties, name, description },
        ValidatorConfigurationV2
      );
      const definition = wrapDefinitionV2(newDefinition);
      setDefinition(definition);
      debugger;
      saveWorkflow(definition, true);
      router.back();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [nodes, edges, v2Properties, ValidatorConfigurationV2]
  );

  if (isLoading) {
    return (
      <Card className={`p-4 md:p-10 mx-auto max-w-7xl mt-6`}>
        <EmptyBuilderState />
      </Card>
    );
  }

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
      <CopilotKit runtimeUrl="/api/copilotkit">
        {getworkflowStatus()}
        <Card className="mt-2 p-0 h-[90%] overflow-hidden">
          <ResizableColumns
            leftClassName=""
            rightClassName=""
            leftChild={
              <div className="flex-1 h-full relative">
                <ReactFlowProvider>
                  <ReactFlowBuilder
                    providers={providers}
                    installedProviders={installedProviders}
                    definition={definition}
                    validatorConfiguration={ValidatorConfigurationV2}
                    onDefinitionChange={setWrappedDefinition}
                    toolboxConfiguration={getToolboxConfiguration(providers)}
                  />
                </ReactFlowProvider>
              </div>
            }
            rightChild={
              <BuilderChat
                definition={definition}
                installedProviders={installedProviders ?? []}
              />
            }
            initialLeftWidth={60}
          />
        </Card>
      </CopilotKit>
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => router.back()}
        className="w-[600px]"
        title="Edit Workflow Metadata"
      >
        <EditWorkflowMetadataForm
          workflow={{
            id: v2Properties.id,
            name: v2Properties.name,
            description: v2Properties.description,
          }}
          onCancel={() => router.back()}
          onSubmit={updateWorkflowMetadata}
        />
      </Modal>
    </div>
  );
}

export default Builder;
