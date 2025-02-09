import { useEffect, useState } from "react";
import { Callout, Card } from "@tremor/react";
import { Provider } from "../../providers/providers";
import { getToolboxConfiguration } from "./utils";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/20/solid";
import { EmptyBuilderState } from "./empty-builder-state";
import { useSearchParams } from "next/navigation";
import BuilderWorkflowTestRunModalContent from "./builder-workflow-testrun-modal";
import {
  WorkflowExecutionDetail,
  WorkflowExecutionFailure,
} from "@/shared/api/workflow-executions";
import ReactFlowBuilder from "./ReactFlowBuilder";
import { ReactFlowProvider } from "@xyflow/react";
import { KeepApiError } from "@/shared/api";
import { CopilotKit } from "@copilotkit/react-core";
import { BuilderChat } from "./builder-chat";
import Modal from "@/components/ui/Modal";
import ResizableColumns from "@/components/ui/ResizableColumns";
import { useWorkflowActions } from "@/entities/workflows";
import { useWorkflowStore } from "./workflow-store";

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
  const [testRunModalOpen, setTestRunModalOpen] = useState(false);
  const [runningWorkflowExecution, setRunningWorkflowExecution] = useState<
    WorkflowExecutionDetail | WorkflowExecutionFailure | null
  >(null);

  // TODO: move to context?
  const { testWorkflow } = useWorkflowActions();

  const searchParams = useSearchParams();
  const { v2Properties, updateV2Properties, nodes, edges, definition } =
    useWorkflowStore();

  const initialize = useWorkflowStore((s) => s.initialize);
  const initializeEmpty = useWorkflowStore((s) => s.initializeEmpty);

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

  useEffect(() => {
    if (loadedAlertFile) {
      initialize(loadedAlertFile, providers);
    } else {
      const alertName = searchParams?.get("alertName");
      const alertSource = searchParams?.get("alertSource");

      initializeEmpty({
        alertName,
        alertSource,
      });
    }
  }, [loadedAlertFile, providers]);

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
