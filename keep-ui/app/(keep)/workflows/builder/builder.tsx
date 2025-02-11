import { useCallback, useEffect, useMemo, useState } from "react";
import { Callout, Card } from "@tremor/react";
import { Provider } from "../../providers/providers";
import {
  parseWorkflow,
  generateWorkflow,
  getWorkflowFromDefinition,
  wrapDefinitionV2,
  getToolboxConfiguration,
} from "./utils";
import { stringify } from "yaml";
import { useRouter, useSearchParams } from "next/navigation";
import { v4 as uuidv4 } from "uuid";
import BuilderWorkflowTestRunModalContent from "./builder-workflow-testrun-modal";
import {
  WorkflowExecutionDetail,
  WorkflowExecutionFailure,
} from "@/shared/api/workflow-executions";
import ReactFlowBuilder from "./ReactFlowBuilder";
import { ReactFlowProvider } from "@xyflow/react";
import useStore from "./builder-store";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/api";
import { ResizableColumns, showErrorToast } from "@/shared/ui";
import { YAMLException } from "js-yaml";
import Modal from "@/components/ui/Modal";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
import Loading from "../../loading";
import MonacoYAMLEditor from "@/shared/ui/YAMLCodeblock/ui/MonacoYAMLEditor";
import Skeleton from "react-loading-skeleton";
interface Props {
  loadedAlertFile: string | null;
  providers: Provider[];
  workflow?: string;
  workflowId?: string;
  installedProviders?: Provider[] | undefined | null;
}

function Builder({
  loadedAlertFile,
  providers,
  workflow,
  workflowId,
  installedProviders,
}: Props) {
  const api = useApi();
  const [testRunModalOpen, setTestRunModalOpen] = useState(false);
  const [runningWorkflowExecution, setRunningWorkflowExecution] = useState<
    WorkflowExecutionDetail | WorkflowExecutionFailure | null
  >(null);
  const { createWorkflow, updateWorkflow } = useWorkflowActions();
  const {
    // Definition
    definition,
    setDefinition,
    isLoading,
    setIsLoading,
    // UI State
    saveRequestCount,
    runRequestCount,
    setIsSaving,
    synced,
    reset,
    canDeploy,
    initializeWorkflow,
  } = useStore();
  const router = useRouter();

  const searchParams = useSearchParams();

  const testRunWorkflow = () => {
    if (!definition?.value) {
      showErrorToast(new Error("Workflow is not initialized"));
      return;
    }
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

  const toolboxConfiguration = useMemo(
    () => getToolboxConfiguration(providers ?? []),
    [providers]
  );

  // TODO: move to useWorkflowInitialization
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
          initializeWorkflow(workflowId ?? null, toolboxConfiguration);
        } else if (loadedAlertFile == null) {
          const alertUuid = uuidv4();
          const alertName = searchParams?.get("alertName");
          const alertSource = searchParams?.get("alertSource");
          let triggers = {};
          if (alertName && alertSource) {
            triggers = { alert: { source: alertSource, name: alertName } };
          }
          // Set empty definition to initialize the store
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
          initializeWorkflow(workflowId ?? null, toolboxConfiguration);
        } else {
          const parsedDefinition = parseWorkflow(loadedAlertFile!, providers);
          setDefinition(
            wrapDefinitionV2({
              ...parsedDefinition,
              isValid: true,
            })
          );
          initializeWorkflow(workflowId ?? null, toolboxConfiguration);
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
  const workflowYaml = useMemo(() => {
    if (!definition?.value) {
      return null;
    }
    return stringify({ workflow: getWorkflowFromDefinition(definition.value) });
  }, [definition?.value]);

  useEffect(() => {
    if (runRequestCount) {
      testRunWorkflow();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runRequestCount]);

  // TODO: move to useWorkflowInitialization or somewhere upper
  const saveWorkflow = useCallback(async () => {
    if (!definition?.value) {
      showErrorToast(new Error("Workflow is not initialized"));
      return;
    }
    if (!synced) {
      showErrorToast(
        new Error(
          "Please save the previous step or wait while properties sync with the workflow."
        )
      );
      return;
    }
    if (!canDeploy) {
      showErrorToast(
        new Error("Please fix the errors in the workflow before saving.")
      );
      return;
    }
    try {
      setIsSaving(true);
      if (workflowId) {
        await updateWorkflow(workflowId, definition.value);
        // TODO: mark workflow as deployed to cloud
      } else {
        const response = await createWorkflow(definition.value);
        if (response?.workflow_id) {
          router.push(`/workflows/${response.workflow_id}`);
        }
      }
    } catch (error) {
      console.error(error);
      showErrorToast(error);
    } finally {
      setIsSaving(false);
    }
  }, [
    synced,
    canDeploy,
    definition?.value,
    setIsSaving,
    workflowId,
    updateWorkflow,
    createWorkflow,
    router,
  ]);

  // save workflow on "Deploy" button click
  useEffect(() => {
    if (saveRequestCount) {
      saveWorkflow();
    }
    // ignore since we want the latest values, but to run effect only when triggerSave changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saveRequestCount]);

  useEffect(
    function resetZustandStateOnUnMount() {
      return () => {
        reset();
      };
    },
    [reset]
  );

  if (isLoading) {
    return (
      <Card className={`p-4 md:p-10 mx-auto max-w-7xl mt-6`}>
        <Loading loadingText="Loading workflow..." />
      </Card>
    );
  }

  const closeWorkflowExecutionResultsModal = () => {
    setTestRunModalOpen(false);
    setRunningWorkflowExecution(null);
  };

  return (
    <>
      <div className="h-full">
        <Card className="mt-2 p-0 h-full overflow-hidden">
          <ResizableColumns
            leftChild={
              workflowYaml ? (
                <MonacoYAMLEditor
                  key={workflowYaml}
                  workflowRaw={workflowYaml}
                  filename={workflowId ?? "workflow"}
                  workflowId={workflowId}
                  // TODO: support readOnly for not yet deployed workflows
                  readOnly={!workflowId}
                />
              ) : (
                <Skeleton className="w-full h-full" />
              )
            }
            initialLeftWidth={33}
            rightChild={
              <div className="flex h-full">
                <div className="flex-1 h-full relative">
                  <ReactFlowProvider>
                    <ReactFlowBuilder
                      providers={providers}
                      installedProviders={installedProviders}
                    />
                  </ReactFlowProvider>
                </div>
              </div>
            }
          />
        </Card>
      </div>
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
    </>
  );
}

export default Builder;
