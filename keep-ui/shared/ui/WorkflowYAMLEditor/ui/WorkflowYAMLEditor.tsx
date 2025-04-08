"use client";

import React, { Suspense, useMemo, useRef, useState } from "react";
import type { editor, Uri } from "monaco-editor";
import { Download, Copy, Check } from "lucide-react";
import { Button } from "@tremor/react";
import { useWorkflowJsonSchema } from "@/entities/workflows/lib/useWorkflowJsonSchema";
import { KeepLoader } from "@/shared/ui";
import { downloadFileFromString } from "@/shared/lib/downloadFileFromString";
import { YamlValidationError } from "../model/types";
import { WorkflowYAMLValidationErrors } from "./WorkflowYAMLValidationErrors";
import clsx from "clsx";

// NOTE: IT IS IMPORTANT TO IMPORT FROM THE SHARED UI DIRECTORY, because import will be replaced for turbopack
import { MonacoYAMLEditor } from "@/shared/ui";
import { getSeverityString, MarkerSeverity } from "../lib/utils";

const KeepSchemaPath = "file:///workflow-schema.json";

interface BaseWorkflowYAMLEditorProps {
  workflowId?: string;
  filename?: string;
  readOnly?: boolean;
  "data-testid"?: string;
  onMount?: (
    editor: editor.IStandaloneCodeEditor,
    monacoInstance: typeof import("monaco-editor")
  ) => void;
  onChange?: (value: string | undefined) => void;
  onValidationErrors?: (errors: YamlValidationError[]) => void;
  onSave?: (value: string) => void;
}

export type WorkflowYAMLEditorProps =
  | (BaseWorkflowYAMLEditorProps & {
      value: string;
    })
  | (BaseWorkflowYAMLEditorProps & {
      original: string;
      modified: string;
    });

export const WorkflowYAMLEditor = ({
  workflowId,
  filename = "workflow",
  readOnly = false,
  "data-testid": dataTestId = "yaml-editor",
  onMount,
  onChange,
  onSave,
  onValidationErrors,
  ...props
}: WorkflowYAMLEditorProps) => {
  const monacoRef = useRef<typeof import("monaco-editor") | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const [validationErrors, setValidationErrors] = useState<
    YamlValidationError[] | null
  >(null);
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

  const handleMarkersChanged = (
    modelUri: Uri,
    markers: editor.IMarker[] | editor.IMarkerData[]
  ) => {
    const editorUri = editorRef.current!.getModel()?.uri;
    if (modelUri.path !== editorUri?.path) {
      return;
    }
    const errors = [];
    for (const marker of markers) {
      if (marker.severity === MarkerSeverity.Hint) {
        continue;
      }
      errors.push({
        message: marker.message,
        severity: getSeverityString(marker.severity),
        lineNumber: marker.startLineNumber,
        column: marker.startColumn,
      });
    }
    setValidationErrors(errors);
    onValidationErrors?.(errors);
  };

  const handleEditorDidMount = (
    editor: editor.IStandaloneCodeEditor,
    monacoInstance: typeof import("monaco-editor")
  ) => {
    editorRef.current = editor;
    monacoRef.current = monacoInstance;

    editor.updateOptions({
      glyphMargin: true,
    });

    onMount?.(editor, monacoInstance);

    // Monkey patching to set the initial markers
    // https://github.com/suren-atoyan/monaco-react/issues/70#issuecomment-760389748
    const setModelMarkers = monacoInstance.editor.setModelMarkers;
    monacoInstance.editor.setModelMarkers = function (model, owner, markers) {
      setModelMarkers.call(monacoInstance.editor, model, owner, markers);
      handleMarkersChanged(model.uri, markers);
    };

    setIsEditorMounted(true);
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
    fontSize: 13,
    renderWhitespace: "all",
    wordWrap: "on",
    wordWrapColumn: 80,
    wrappingIndent: "indent",
    theme: "vs-light",
    lineNumbersMinChars: 2,
    folding: false,
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
        className="w-full h-full flex flex-col relative min-h-0"
        data-testid={dataTestId + "-container"}
      >
        <div
          className="flex-1 min-h-0"
          style={{ height: "calc(100vh - 300px)" }}
        >
          <div className={clsx("absolute top-2 right-6 z-10 flex gap-2")}>
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
                <Check className="h-4 w-4" />
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
            {!readOnly && onSave ? (
              <Button
                color="orange"
                size="sm"
                className="h-8 px-2"
                onClick={() => onSave(editorRef.current?.getValue() ?? "")}
                variant="primary"
                data-testid="save-yaml-button"
              >
                Save
              </Button>
            ) : null}
          </div>
          <Suspense
            fallback={<KeepLoader loadingText="Loading YAML editor..." />}
          >
            <MonacoYAMLEditor
              height="100%"
              className="[&_.monaco-editor]:outline-none [&_.decorationsOverviewRuler]:z-2"
              wrapperProps={{ "data-testid": dataTestId }}
              onMount={handleEditorDidMount}
              onChange={onChange}
              options={editorOptions}
              loading={<KeepLoader loadingText="Loading YAML editor..." />}
              theme="light"
              schemas={schemas}
              {...props}
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
    </>
  );
};
