import { useEffect, useState } from "react";
import { Callout, Card } from "@tremor/react";
import { Provider } from "../../providers/providers";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/20/solid";
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
import Loading from "../../loading";

interface Props {
  providers: Provider[];
  workflowRaw?: string;
  workflowId?: string;
  installedProviders?: Provider[] | undefined | null;
}

export function Builder({
  providers,
  workflowRaw,
  workflowId,
  installedProviders,
}: Props) {
  const [testRunModalOpen, setTestRunModalOpen] = useState(false);
  const [runningWorkflowExecution, setRunningWorkflowExecution] = useState<
    WorkflowExecutionDetail | WorkflowExecutionFailure | null
  >(null);

  // TODO: move to context?
  const { testWorkflow } = useWorkflowActions();

  const {
    nodes,
    edges,
    definition,
    runRequestCount,
    validationErrors,
    isLoading,
  } = useWorkflowStore();

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
    if (runRequestCount > 0) {
      testRunWorkflow();
    }
  }, [runRequestCount]);

  console.log("nodes.length=", nodes.length);
  console.log("edges.length=", edges.length);

  if (isLoading) {
    return <Loading loadingText="Initializing workflow builder..." />;
  }

  const closeWorkflowExecutionResultsModal = () => {
    setTestRunModalOpen(false);
    setRunningWorkflowExecution(null);
  };

  const getworkflowStatus = () => {
    return (
      <div className="">
        {Object.values(validationErrors).some((error) => error !== null) ? (
          <Callout
            title={`Validation Error${Object.values(validationErrors).length > 1 ? "s" : ""}`}
            icon={ExclamationCircleIcon}
            color="rose"
          >
            {Object.entries(validationErrors)
              .filter(([key, value]) => value !== null)
              .map(([key, value]) => (
                <div key={key}>
                  <span className="font-bold">{key}:</span> {value}
                </div>
              ))}
          </Callout>
        ) : (
          <Callout
            title="Schema is valid"
            icon={CheckCircleIcon}
            color="teal"
          ></Callout>
        )}
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col gap-2">
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
          workflowRaw={workflowRaw ?? ""}
          workflowId={workflowId ?? ""}
        />
      </Modal>
    </div>
  );
}
