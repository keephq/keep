import { useCallback, useEffect, useState } from "react";
import { Callout, Card } from "@tremor/react";
import { Provider } from "../../providers/providers";
import {
  parseWorkflow,
  generateWorkflow,
  getToolboxConfiguration,
  getWorkflowFromDefinition,
  wrapDefinitionV2,
  getDefinitionFromNodesEdgesProperties,
} from "./utils";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/20/solid";
import { LegacyWorkflow } from "./legacy-workflow.types";
import BuilderModalContent from "./builder-modal";
import { EmptyBuilderState } from "./empty-builder-state";
import { useRouter, useSearchParams } from "next/navigation";
import { v4 as uuidv4 } from "uuid";
import BuilderWorkflowTestRunModalContent from "./builder-workflow-testrun-modal";
import {
  WorkflowExecutionDetail,
  WorkflowExecutionFailure,
} from "@/shared/api/workflow-executions";
import ReactFlowBuilder from "./ReactFlowBuilder";
import { ReactFlowProvider } from "@xyflow/react";
import { useStore } from "./builder-store";
import { KeepApiError } from "@/shared/api";
import { showErrorToast } from "@/shared/ui";
import { YAMLException } from "js-yaml";
import { CopilotKit } from "@copilotkit/react-core";
import { BuilderChat } from "./builder-chat";
import Modal from "@/components/ui/Modal";
import { useWorkflowBuilderContext } from "./workflow-builder-context";
import ResizableColumns from "@/components/ui/ResizableColumns";
import { EditWorkflowMetadataForm } from "@/features/edit-workflow-metadata";
import { useWorkflowActions } from "@/entities/workflows";

interface Props {
  loadedAlertFile: string | null;
  providers: Provider[];
  workflow?: string;
  workflowId?: string;
  installedProviders?: Provider[] | undefined | null;
}

export function Builder({
  loadedAlertFile,
  providers,
  workflow,
  workflowId,
  installedProviders,
}: Props) {
  const [isLoading, setIsLoading] = useState(true);
  const [generateModalIsOpen, setGenerateModalIsOpen] = useState(false);
  const [testRunModalOpen, setTestRunModalOpen] = useState(false);
  const [runningWorkflowExecution, setRunningWorkflowExecution] = useState<
    WorkflowExecutionDetail | WorkflowExecutionFailure | null
  >(null);
  const [legacyWorkflow, setLegacyWorkflow] = useState<LegacyWorkflow | null>(
    null
  );

  // TODO: move to context?
  const { updateWorkflow, testWorkflow } = useWorkflowActions();

  const {
    definition,
    setDefinition,
    generateRequestCount,
    runRequestCount,
    validatorConfigurationV2,
    stepValidationError,
    globalValidationError,
  } = useWorkflowBuilderContext();
  const router = useRouter();

  const searchParams = useSearchParams();
  const isEditModalOpen = searchParams.get("edit") === "true";
  const { v2Properties, updateV2Properties, nodes, edges } = useStore();

  const testRunWorkflow = async () => {
    setTestRunModalOpen(true);
    try {
      const response = await testWorkflow(definition.value);
      setRunningWorkflowExecution({
        ...response,
      });
    } catch (error) {
      setRunningWorkflowExecution({
        error: error instanceof KeepApiError ? error.message : "Unknown error",
      });
    }
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

  // TODO: depricate this in favor of YML tab
  useEffect(() => {
    if (generateRequestCount) {
      setLegacyWorkflow(getWorkflowFromDefinition(definition.value));
      if (!generateModalIsOpen) {
        setGenerateModalIsOpen(true);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [generateRequestCount]);

  useEffect(() => {
    if (runRequestCount) {
      testRunWorkflow();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runRequestCount]);

  console.log("nodes.length=", nodes.length);
  console.log("edges.length=", edges.length);

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
                    toolboxConfiguration={getToolboxConfiguration(providers)}
                  />
                </ReactFlowProvider>
              </div>
            }
            rightChild={
              <BuilderChat
                definition={definition}
                installedProviders={installedProviders}
              />
            }
            initialLeftWidth={60}
          />
        </Card>
      </CopilotKit>
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
    </div>
  );
}
