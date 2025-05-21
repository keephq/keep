"use client";

import React, {
  Suspense,
  useMemo,
  useRef,
  useState,
  useCallback,
  useEffect,
} from "react";
import type { editor } from "monaco-editor";
import { useWorkflowJsonSchema } from "@/entities/workflows/lib/useWorkflowJsonSchema";
import { WorkflowYAMLEditorProps } from "../model/types";
// NOTE: IT IS IMPORTANT TO IMPORT MonacoYAMLEditor FROM THE SHARED UI DIRECTORY, because import will be replaced for turbopack
import {
  MonacoYAMLEditor,
  KeepLoader,
  showErrorToast,
  showSuccessToast,
} from "@/shared/ui";
import { downloadFileFromString } from "@/shared/lib/downloadFileFromString";
import { WorkflowYAMLValidationErrors } from "./WorkflowYAMLValidationErrors";
import { useYamlValidation } from "../lib/useYamlValidation";
import { WorkflowYAMLEditorToolbar } from "./WorkflowYAMLEditorToolbar";
import { navigateToErrorPosition } from "../lib/utils";
import { useWorkflowSecrets } from "@/utils/hooks/useWorkflowSecrets";
import { Link } from "@/components/ui/Link";
import { DOCS_CLIPBOARD_COPY_ERROR_PATH } from "@/shared/constants";
import { useConfig } from "@/utils/hooks/useConfig";

const KeepSchemaPath = "file:///workflow-schema.json";

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
  const editorRef = useRef<
    editor.IStandaloneCodeEditor | editor.IDiffEditor | null
  >(null);
  const { getSecrets } = useWorkflowSecrets(workflowId);
  const { data: secrets } = getSecrets;
  const { data: config } = useConfig();

  const {
    validationErrors,
    validateMustacheExpressions,
    handleMarkersChanged,
  } = useYamlValidation({
    onValidationErrors,
  });

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

  const getEditorValue = useCallback(() => {
    if (!editorRef.current) {
      return;
    }
    const model = editorRef.current.getModel();
    if (!model) {
      return;
    }
    if ("original" in model) {
      return model.modified.getValue();
    }
    return model.getValue();
  }, []);

  const validateMustacheExpressionsEverywhere = useCallback(() => {
    if (editorRef.current && monacoRef.current) {
      const model = editorRef.current.getModel();
      if (!model) {
        return;
      }
      if ("original" in model) {
        validateMustacheExpressions(
          model.original,
          monacoRef.current,
          secrets ?? {}
        );
        validateMustacheExpressions(
          model.modified,
          monacoRef.current,
          secrets ?? {}
        );
      } else {
        validateMustacheExpressions(model, monacoRef.current, secrets ?? {});
      }
    }
  }, [validateMustacheExpressions, secrets]);

  const handleChange = useCallback(
    (value: string | undefined) => {
      if (onChange) {
        onChange(value);
      }
      validateMustacheExpressionsEverywhere();
    },
    [onChange, validateMustacheExpressionsEverywhere]
  );

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
      handleMarkersChanged(editor, model.uri, markers, owner);
    };

    setIsEditorMounted(true);
  };

  useEffect(() => {
    // After editor is mounted, validate the initial content
    if (isEditorMounted && editorRef.current && monacoRef.current) {
      validateMustacheExpressionsEverywhere();
    }
  }, [validateMustacheExpressionsEverywhere, isEditorMounted]);

  const downloadYaml = useCallback(() => {
    const value = getEditorValue();
    if (!value) {
      return;
    }
    downloadFileFromString({
      data: value,
      filename: `${filename}.yaml`,
      contentType: "text/yaml",
    });
  }, [filename]);

  const copyToClipboard = useCallback(async () => {
    const value = getEditorValue();
    if (!value) {
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      showSuccessToast("Workflow YAML copied to clipboard");
    } catch (err) {
      showErrorToast(
        err,
        <p>
          Failed to copy Workflow YAML. Please check your browser permissions.{" "}
          <Link
            target="_blank"
            href={`${config?.KEEP_DOCS_URL}${DOCS_CLIPBOARD_COPY_ERROR_PATH}`}
          >
            Learn more
          </Link>
        </p>
      );
    }
  }, []);

  const handleSave = useCallback(() => {
    const value = getEditorValue();
    if (!onSave || !value) {
      return;
    }
    onSave(value);
  }, [onSave]);

  const editorOptions = useMemo<editor.IStandaloneEditorConstructionOptions>(
    () => ({
      readOnly,
      minimap: { enabled: false },
      lineNumbers: "on",
      glyphMargin: true,
      scrollBeyondLastLine: false,
      automaticLayout: true,
      tabSize: 2,
      lineNumbersMinChars: 2,
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
    }),
    [readOnly]
  );

  return (
    <div
      className="w-full h-full flex flex-col relative min-h-0"
      data-testid={dataTestId + "-container"}
    >
      <div className="flex-1 min-h-0" style={{ height: "calc(100vh - 300px)" }}>
        <WorkflowYAMLEditorToolbar
          onCopy={copyToClipboard}
          onDownload={downloadYaml}
          onSave={onSave ? handleSave : undefined}
          isEditorMounted={isEditorMounted}
          readOnly={readOnly}
        />
        <Suspense
          fallback={<KeepLoader loadingText="Loading YAML editor..." />}
        >
          <MonacoYAMLEditor
            height="100%"
            className="[&_.monaco-editor]:outline-none [&_.decorationsOverviewRuler]:z-2"
            wrapperProps={{ "data-testid": dataTestId }}
            onMount={handleEditorDidMount}
            onChange={handleChange}
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
            //
          }
          navigateToErrorPosition(
            editorRef.current,
            error.lineNumber,
            error.column
          );
        }}
      />
      <div className="flex items-center justify-between px-4 py-2 border-t border-gray-200">
        <span className="text-sm text-gray-500">{filename}.yaml</span>
        {workflowId && (
          <span className="text-sm text-gray-500">{workflowId}</span>
        )}
      </div>
    </div>
  );
};
