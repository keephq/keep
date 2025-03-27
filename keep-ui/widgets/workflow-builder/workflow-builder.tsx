import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Card } from "@tremor/react";
import { Provider } from "@/shared/api/providers";
import { useRouter, useSearchParams } from "next/navigation";
import { v4 as uuidv4 } from "uuid";
import ReactFlowBuilder from "@/features/workflows/builder/ui/ReactFlowBuilder";
import { ReactFlowProvider } from "@xyflow/react";
import { useWorkflowStore } from "@/entities/workflows";
import { showErrorToast, KeepLoader } from "@/shared/ui";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
import { WorkflowYAMLEditor } from "@/shared/ui";
import {
  getWorkflowDefinition,
  getYamlWorkflowDefinition,
  parseWorkflow,
  wrapDefinitionV2,
} from "@/entities/workflows/lib/parser";
import { CodeBracketIcon, SparklesIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";
import { ResizableColumns } from "@/shared/ui";
import { WorkflowBuilderChatSafe } from "@/features/workflows/ai-assistant";
import debounce from "lodash.debounce";
import { getOrderedWorkflowYamlStringFromJSON } from "@/entities/workflows/lib/yaml-utils";
import { useWorkflowSecrets } from "@/utils/hooks/useWorkflowSecrets";

interface Props {
  loadedYamlFileContents: string | null;
  providers: Provider[];
  workflowRaw?: string;
  workflowId?: string;
  installedProviders?: Provider[] | undefined | null;
}

export function WorkflowBuilder({
  loadedYamlFileContents,
  providers,
  workflowRaw,
  workflowId,
  installedProviders,
}: Props) {
  const { createWorkflow, updateWorkflow } = useWorkflowActions();
  const {
    getSecrets: { data: workflowSecrets },
  } = useWorkflowSecrets(workflowId ?? null);
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
    setProviders,
    setInstalledProviders,
    setSecrets,
    updateFromYamlString,
  } = useWorkflowStore();
  const router = useRouter();

  const [leftColumnMode, setLeftColumnMode] = useState<"yaml" | "chat" | null>(
    "chat"
  );

  const searchParams = useSearchParams();

  useEffect(
    function syncProviders() {
      setProviders(providers);
      setInstalledProviders(installedProviders ?? []);
    },
    // setProviders and setInstalledProviders shouldn't change
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [providers, installedProviders]
  );

  useEffect(
    function syncSecrets() {
      setSecrets(workflowSecrets ?? {});
    },
    [workflowSecrets]
  );

  // TODO: move to workflow initialization
  useEffect(
    function updateDefinitionFromInput() {
      setIsLoading(true);
      try {
        if (workflowRaw) {
          setDefinition(
            wrapDefinitionV2({
              ...parseWorkflow(workflowRaw, providers),
              isValid: true,
            })
          );
          initializeWorkflow(workflowId ?? null, {
            providers,
            installedProviders: installedProviders ?? [],
            secrets: workflowSecrets ?? {},
          });
        } else if (loadedYamlFileContents == null) {
          const alertUuid = uuidv4();
          const alertName = searchParams?.get("alertName");
          const alertSource = searchParams?.get("alertSource");
          let triggers = {};
          if (alertName && alertSource) {
            triggers = { alert: { source: alertSource, name: alertName } };
          }
          const definition = getWorkflowDefinition(
            alertUuid,
            "",
            "",
            false,
            {},
            [],
            [],
            triggers
          );
          const wrappedDefinition = wrapDefinitionV2({
            ...definition,
            isValid: true,
          });
          setDefinition(wrappedDefinition);
          initializeWorkflow(workflowId ?? null, {
            providers,
            installedProviders: installedProviders ?? [],
            secrets: workflowSecrets ?? {},
          });
        } else {
          const parsedDefinition = parseWorkflow(
            loadedYamlFileContents!,
            providers
          );
          setDefinition(
            wrapDefinitionV2({
              ...parsedDefinition,
              isValid: true,
            })
          );
          initializeWorkflow(workflowId ?? null, {
            providers,
            installedProviders: installedProviders ?? [],
            secrets: workflowSecrets ?? {},
          });
        }
      } catch (error) {
        showErrorToast(error, "Failed to load workflow");
      }
      setIsLoading(false);
    },
    [loadedYamlFileContents, workflowRaw, searchParams, providers]
  );

  const workflowYaml = useMemo(() => {
    if (!definition?.value) {
      return null;
    }
    return getOrderedWorkflowYamlStringFromJSON({
      workflow: getYamlWorkflowDefinition(definition.value),
    });
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

  const lastSaveRequestCount = useRef(saveRequestCount);
  // save workflow on "Deploy" button click
  useEffect(() => {
    if (saveRequestCount && saveRequestCount !== lastSaveRequestCount.current) {
      saveWorkflow();
      lastSaveRequestCount.current = saveRequestCount;
    }
    // ignore since we want the latest values, but to run effect only when triggerSave changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saveRequestCount]);

  useEffect(function resetZustandStateOnUnMount() {
    return () => {
      console.log("resetting zustand state");
      reset();
    };
  }, []);

  const handleYamlChange = useMemo(
    () =>
      debounce((yamlString: string | undefined) => {
        if (!yamlString) {
          return;
        }
        updateFromYamlString(yamlString);
      }, 1000),
    [updateFromYamlString]
  );

  if (isLoading) {
    return (
      <Card className={`p-4 md:p-10 mx-auto max-w-7xl mt-6`}>
        <KeepLoader loadingText="Loading workflow..." />
      </Card>
    );
  }

  return (
    <ResizableColumns initialLeftWidth={leftColumnMode !== null ? 33 : 0}>
      <>
        <div
          className={clsx(
            leftColumnMode === "yaml" ? "visible h-full" : "hidden"
          )}
        >
          <WorkflowYAMLEditor
            workflowYamlString={workflowYaml ?? ""}
            filename={workflowId ?? "workflow"}
            workflowId={workflowId}
            data-testid="wf-builder-yaml-editor"
            onChange={handleYamlChange}
          />
        </div>
        <div
          className={clsx(
            leftColumnMode === "chat" ? "visible h-full" : "hidden"
          )}
        >
          <WorkflowBuilderChatSafe
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
                  data-testid="wf-close-yaml-editor-button"
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
