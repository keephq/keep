import { useCallback, useEffect, useMemo, useState } from "react";
import { Card } from "@tremor/react";
import { Provider } from "@/app/(keep)/providers/providers";
import { getToolboxConfiguration } from "@/features/workflows/builder/lib/utils";
import { stringify } from "yaml";
import { useRouter, useSearchParams } from "next/navigation";
import { v4 as uuidv4 } from "uuid";
import ReactFlowBuilder from "@/features/workflows/builder/ui/ReactFlowBuilder";
import { ReactFlowProvider } from "@xyflow/react";
import { useWorkflowStore } from "@/entities/workflows";
import { ResizableColumns, showErrorToast, KeepLoader } from "@/shared/ui";
import { YAMLException } from "js-yaml";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
import MonacoYAMLEditor from "@/shared/ui/YAMLCodeblock/ui/MonacoYAMLEditor";
import Skeleton from "react-loading-skeleton";
import {
  generateWorkflow,
  getWorkflowFromDefinition,
  parseWorkflow,
  wrapDefinitionV2,
} from "@/entities/workflows/lib/parser";
import clsx from "clsx";
import { ChevronLeftIcon, CodeBracketIcon } from "@heroicons/react/24/outline";

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
  const { createWorkflow, updateWorkflow } = useWorkflowActions();
  const {
    // Definition
    definition,
    setDefinition,
    isLoading,
    setIsLoading,
    // UI State
    saveRequestCount,
    setIsSaving,
    synced,
    reset,
    canDeploy,
    initializeWorkflow,
  } = useWorkflowStore();
  const router = useRouter();

  const [isYamlEditorOpen, setIsYamlEditorOpen] = useState(true);

  const searchParams = useSearchParams();

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
        <KeepLoader loadingText="Loading workflow..." />
      </Card>
    );
  }

  return (
    <ResizableColumns
      key={isYamlEditorOpen ? "yaml-editor-open" : "yaml-editor-closed"}
      leftChild={
        isYamlEditorOpen ? (
          workflowYaml ? (
            <MonacoYAMLEditor
              // TODO: do not re-render editor on every workflowYaml change, handle updates inside the editor
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
        ) : null
      }
      initialLeftWidth={isYamlEditorOpen ? 33 : 0}
      rightChild={
        <div className="relative h-full">
          <div className={clsx("absolute top-0 left-0 w-10 h-10 z-50")}>
            {!isYamlEditorOpen ? (
              <button
                className="flex justify-center items-center bg-white w-full h-full border-b border-r rounded-br-lg shadow-md"
                onClick={() => setIsYamlEditorOpen(true)}
                data-testid="wf-open-editor-button"
                title="Show YAML editor"
              >
                <CodeBracketIcon className="size-5" />
              </button>
            ) : (
              <div className="flex gap-0.5 h-full">
                <button
                  className="flex justify-center bg-white items-center w-full h-full border-b border-r rounded-br-lg shadow-md"
                  onClick={() => setIsYamlEditorOpen(false)}
                  data-testid="wf-close-editor-button"
                  title="Hide YAML editor"
                >
                  <ChevronLeftIcon className="size-5" />
                </button>
              </div>
            )}
          </div>
          <ReactFlowProvider>
            <ReactFlowBuilder
              providers={providers}
              installedProviders={installedProviders}
            />
          </ReactFlowProvider>
        </div>
      }
    />
  );
}

export default Builder;
