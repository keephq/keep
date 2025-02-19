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
import { showErrorToast, KeepLoader } from "@/shared/ui";
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
import { CodeBracketIcon, SparklesIcon } from "@heroicons/react/24/outline";
import { BuilderChatSafe } from "@/features/workflows/builder/ui/BuilderChat/builder-chat";
import clsx from "clsx";
import { ResizableColumns } from "@/shared/ui";
import { useConfig } from "@/utils/hooks/useConfig";

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
    setLastDeployedAt,
    isEditorSyncedWithNodes: synced,
    reset,
    canDeploy,
    initializeWorkflow,
  } = useWorkflowStore();
  const router = useRouter();

  const { data: configData } = useConfig();
  const isAIEnabled = configData?.OPEN_AI_API_KEY_SET;

  const [leftColumnMode, setLeftColumnMode] = useState<"yaml" | "chat" | null>(
    isAIEnabled ? "chat" : "yaml"
  );

  const searchParams = useSearchParams();

  const toolboxConfiguration = useMemo(
    () => getToolboxConfiguration(providers ?? []),
    [providers]
  );

  // TODO: move to workflow initialization
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

  // TODO: move to workflow initialization or somewhere upper
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
      setLastDeployedAt(Date.now());
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

  const YamlEditor = () => {
    if (!workflowYaml) {
      return <Skeleton className="w-full h-full" />;
    }
    return (
      <MonacoYAMLEditor
        // TODO: do not re-render editor on every workflowYaml change, handle updates inside the editor
        key={workflowYaml}
        workflowRaw={workflowYaml}
        filename={workflowId ?? "workflow"}
        workflowId={workflowId}
        // TODO: support write for not yet deployed workflows
        readOnly={!workflowId}
      />
    );
  };

  return (
    <ResizableColumns initialLeftWidth={leftColumnMode !== null ? 33 : 0}>
      <>
        <div
          className={clsx(
            leftColumnMode === "yaml" ? "visible h-full" : "hidden"
          )}
        >
          <YamlEditor />
        </div>
        <div
          className={clsx(
            leftColumnMode === "chat" ? "visible h-full" : "hidden"
          )}
        >
          <BuilderChatSafe
            definition={definition}
            installedProviders={installedProviders ?? []}
          />
        </div>
      </>
      <>
        <div className="relative h-full">
          <div className={clsx("absolute top-0 left-0 w-10 h-10 z-50")}>
            {leftColumnMode !== "yaml" ? (
              <button
                className="flex justify-center items-center bg-white w-full h-full border-b border-r rounded-br-lg shadow-md"
                onClick={() => setLeftColumnMode("yaml")}
                data-testid="wf-open-editor-button"
                title="Show YAML editor"
              >
                <CodeBracketIcon className="size-5" />
              </button>
            ) : (
              <div className="flex gap-0.5 h-full">
                <button
                  className="flex justify-center bg-white items-center w-full h-full border-b border-r rounded-br-lg shadow-md text-orange-500"
                  onClick={() => setLeftColumnMode(null)}
                  data-testid="wf-close-editor-button"
                  title="Hide YAML editor"
                >
                  <CodeBracketIcon className="size-5" />
                </button>
              </div>
            )}
          </div>
          <div className={clsx("absolute top-10 left-0 w-10 h-10 z-50")}>
            {leftColumnMode !== "chat" ? (
              <button
                className="flex justify-center items-center bg-white w-full h-full border-b border-r rounded-br-lg shadow-md"
                onClick={() => setLeftColumnMode("chat")}
                data-testid="wf-open-chat-button"
                title="Show AI Assistant"
              >
                <SparklesIcon className="size-5" />
              </button>
            ) : (
              <div className="flex gap-0.5 h-full">
                <button
                  className="flex justify-center bg-white items-center w-full h-full border-b border-r rounded-br-lg shadow-md text-orange-500"
                  onClick={() => setLeftColumnMode(null)}
                  data-testid="wf-close-chat-button"
                  title="Hide AI Assistant"
                >
                  <SparklesIcon className="size-5" />
                </button>
              </div>
            )}
          </div>
          <ReactFlowProvider>
            <ReactFlowBuilder />
          </ReactFlowProvider>
        </div>
      </>
    </ResizableColumns>
  );
}

export default Builder;
