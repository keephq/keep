"use client";
import React, {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { editor } from "monaco-editor";
import { Download, Copy, Check, Save } from "lucide-react";
import { Button } from "@tremor/react";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
import { getOrderedWorkflowYamlString } from "@/entities/workflows/lib/yaml-utils";
import { useWorkflowJsonSchema } from "@/entities/workflows/model/useWorkflowJsonSchema";
import { KeepLoader } from "../../KeepLoader/KeepLoader";
import { downloadFileFromString } from "@/shared/lib/downloadFileFromString";
// NOTE: IT IS IMPORTANT TO IMPORT FROM THE SHARED UI DIRECTORY, because import will be replaced for turbopack
import { MonacoYAMLEditor } from "@/shared/ui";
import { YamlValidationError } from "../types";
import { WorkflowYAMLValidationErrors } from "./WorkflowYAMLValidationErrors";
import { WorkflowYamlEditorHeader } from "./WorkflowYamlEditorHeader";
import clsx from "clsx";
import { WorkflowTestRunModal } from "@/features/workflows/test-run/ui/workflow-test-run-modal";
import { DefinitionV2 } from "@/entities/workflows";
import { wrapDefinitionV2 } from "@/entities/workflows/lib/parser";
import { parseWorkflow } from "@/entities/workflows/lib/parser";
import { useProviders } from "@/utils/hooks/useProviders";

const KeepSchemaPath = "file:///workflow-schema.json";

// Copied from monaco-editor/esm/vs/editor/editor.api.d.ts because we can't import with turbopack
enum MarkerSeverity {
  Hint = 1,
  Info = 2,
  Warning = 4,
  Error = 8,
}

export interface WorkflowYAMLEditorProps {
  workflowRaw: string;
  workflowId?: string;
  filename?: string;
  readOnly?: boolean;
  standalone?: boolean;
  "data-testid"?: string;
  onDidMount?: (
    editor: editor.IStandaloneCodeEditor,
    monacoInstance: typeof import("monaco-editor")
  ) => void;
}

export const WorkflowYAMLEditor = ({
  workflowRaw,
  filename = "workflow",
  workflowId,
  readOnly = false,
  standalone = false,
  "data-testid": dataTestId = "yaml-editor",
  onDidMount,
}: WorkflowYAMLEditorProps) => {
  const monacoRef = useRef<typeof import("monaco-editor") | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const [validationErrors, setValidationErrors] = useState<
    YamlValidationError[] | null
  >(null);
  const { updateWorkflow } = useWorkflowActions();
  const [lastDeployedAt, setLastDeployedAt] = useState<number | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const workflowJsonSchema = useWorkflowJsonSchema();
  const schemas = useMemo(() => {
    return [
      {
        fileMatch: ["*"],
        schema: workflowJsonSchema,
        uri: KeepSchemaPath,
      },
    ];
  }, [workflowJsonSchema]);

  const [isEditorMounted, setIsEditorMounted] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [originalContent, setOriginalContent] = useState("");
  const [definition, setDefinition] = useState<DefinitionV2 | null>(null);
  const [runRequestCount, setRunRequestCount] = useState(0);

  const { data: { providers } = {} } = useProviders();

  const parseYamlToDefinition = useCallback(
    (yamlString: string) => {
      try {
        setDefinition(
          wrapDefinitionV2({
            ...parseWorkflow(yamlString, providers ?? []),
            isValid: true,
          })
        );
      } catch (error) {
        console.error("Failed to parse YAML:", error);
      }
    },
    [providers]
  );

  const handleMarkersChanged = (
    markers: editor.IMarker[] | editor.IMarkerData[]
  ) => {
    const errors = [];
    for (const marker of markers) {
      let severityString = "";
      if (marker.severity === MarkerSeverity.Hint) {
        continue;
      }
      if (marker.severity === MarkerSeverity.Warning) {
        severityString = "warning";
      }
      if (marker.severity === MarkerSeverity.Error) {
        severityString = "error";
      }
      if (marker.severity === MarkerSeverity.Info) {
        severityString = "info";
      }
      errors.push({
        message: marker.message,
        severity: severityString as "error" | "warning" | "info",
        lineNumber: marker.startLineNumber,
        column: marker.startColumn,
      });
    }
    setValidationErrors(errors);
  };

  const handleContentChange = (value: string | undefined) => {
    if (!value) {
      return;
    }
    setHasChanges(value !== originalContent);
    parseYamlToDefinition(value);
  };

  // TODO: move logs decoration to helper function or separate component
  const handleEditorDidMount = (
    editor: editor.IStandaloneCodeEditor,
    monacoInstance: typeof import("monaco-editor")
  ) => {
    editorRef.current = editor;
    monacoRef.current = monacoInstance;

    editor.updateOptions({
      glyphMargin: true,
    });

    const model = editor?.getModel();
    if (model) {
      parseYamlToDefinition(model.getValue());
    }

    if (onDidMount) {
      onDidMount(editor, monacoInstance);
    }

    // Monkey patching to set the initial markers
    // https://github.com/suren-atoyan/monaco-react/issues/70#issuecomment-760389748
    const setModelMarkers = monacoInstance.editor.setModelMarkers;
    monacoInstance.editor.setModelMarkers = function (model, owner, markers) {
      setModelMarkers.call(monacoInstance.editor, model, owner, markers);
      handleMarkersChanged(markers);
    };

    setIsEditorMounted(true);
  };

  useEffect(() => {
    setOriginalContent(getOrderedWorkflowYamlString(workflowRaw));
  }, [workflowRaw]);

  const handleSaveWorkflow = async () => {
    if (!editorRef.current) {
      return;
    }
    if (!workflowId) {
      console.error("Workflow ID is required to save the workflow");
      return;
    }
    setIsSaving(true);
    const content = editorRef.current.getValue();
    try {
      // sending the yaml string to the backend
      // TODO: validate the yaml content and show useful (inline) errors
      await updateWorkflow(workflowId, content);

      setOriginalContent(content);
      setHasChanges(false);
    } catch (err) {
      console.error("Failed to save workflow:", err);
    } finally {
      setLastDeployedAt(Date.now());
      setIsSaving(false);
    }
  };

  const downloadYaml = () => {
    if (!editorRef.current) {
      return;
    }
    downloadFileFromString({
      data: editorRef.current.getValue(),
      filename: `${filename}.yaml`,
      contentType: "application/x-yaml",
    });
  };

  const copyToClipboard = async () => {
    if (!editorRef.current) return;
    const content = editorRef.current.getValue();
    try {
      await navigator.clipboard.writeText(content);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text:", err);
    }
  };

  const editorOptions: editor.IStandaloneEditorConstructionOptions = {
    readOnly,
    minimap: { enabled: false },
    lineNumbers: "on",
    glyphMargin: true,
    scrollBeyondLastLine: false,
    automaticLayout: true,
    tabSize: 2,
    insertSpaces: true,
    fontSize: 14,
    renderWhitespace: "all",
    wordWrap: "on",
    wordWrapColumn: 80,
    wrappingIndent: "indent",
    theme: "vs-light",
    quickSuggestions: {
      other: true,
      comments: false,
      strings: true,
    },
    formatOnType: true,
  };

  return (
    <>
      <div
        className="w-full h-full flex flex-col relative"
        data-testid={dataTestId + "-container"}
      >
        {!readOnly && standalone && (
          <WorkflowYamlEditorHeader
            workflowId={workflowId}
            isInitialized={isEditorMounted}
            lastDeployedAt={lastDeployedAt}
            isValid={validationErrors?.length === 0}
            isSaving={isSaving}
            hasChanges={hasChanges}
            onRun={() => {
              setRunRequestCount((prev) => prev + 1);
            }}
            onSave={handleSaveWorkflow}
          />
        )}
        <div
          className="flex-1 min-h-0"
          style={{ height: "calc(100vh - 300px)" }}
        >
          <div
            className={clsx(
              "absolute right-6 z-10 flex gap-2",
              // compensate for the header height, we can't use position: relative, because editor uses position sticky
              standalone ? "top-16" : "top-2"
            )}
          >
            {!readOnly && !standalone && (
              <Button
                color="orange"
                size="sm"
                className="h-8 px-2 bg-white"
                onClick={handleSaveWorkflow}
                variant="secondary"
                disabled={!hasChanges}
                data-testid="save-yaml-button"
              >
                <Save className="h-4 w-4" />
              </Button>
            )}
            <Button
              color="orange"
              size="sm"
              className="h-8 px-2 bg-white"
              onClick={copyToClipboard}
              variant="secondary"
              data-testid="copy-yaml-button"
              disabled={!isEditorMounted}
            >
              {isCopied ? (
                <Check className="h-4 w-4 text-green-500" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </Button>
            <Button
              color="orange"
              size="sm"
              className="h-8 px-2 bg-white"
              onClick={downloadYaml}
              variant="secondary"
              data-testid="download-yaml-button"
              disabled={!isEditorMounted}
            >
              <Download className="h-4 w-4" />
            </Button>
          </div>
          <Suspense
            fallback={<KeepLoader loadingText="Loading YAML editor..." />}
          >
            <MonacoYAMLEditor
              height="100%"
              className="[&_.monaco-editor]:outline-none [&_.decorationsOverviewRuler]:z-2"
              wrapperProps={{ "data-testid": dataTestId }}
              defaultValue={getOrderedWorkflowYamlString(workflowRaw)}
              onMount={handleEditorDidMount}
              onChange={handleContentChange}
              options={editorOptions}
              loading={<KeepLoader loadingText="Loading YAML editor..." />}
              theme="light"
              schemas={schemas}
            />
          </Suspense>
        </div>
        <WorkflowYAMLValidationErrors
          isMounted={isEditorMounted}
          validationErrors={validationErrors}
          onErrorClick={(error) => {
            if (!editorRef.current) {
              return;
            }
            editorRef.current.setPosition({
              lineNumber: error.lineNumber,
              column: error.column,
            });
            editorRef.current.focus();
            editorRef.current.revealLineInCenter(error.lineNumber);
          }}
        />
        <div className="flex items-center justify-between px-4 py-2 border-t border-gray-200">
          <span className="text-sm text-gray-500">{filename}.yaml</span>
          {workflowId && (
            <span className="text-sm text-gray-500">{workflowId}</span>
          )}
        </div>
      </div>
      <WorkflowTestRunModal
        workflowId={workflowId ?? ""}
        definition={definition}
        runRequestCount={runRequestCount}
      />
    </>
  );
};
