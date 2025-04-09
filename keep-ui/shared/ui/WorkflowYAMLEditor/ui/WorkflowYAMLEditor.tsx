"use client";

import React, { Suspense, useMemo, useRef, useState, useCallback } from "react";
import type { editor, Uri } from "monaco-editor";
import { Download, Copy, Check } from "lucide-react";
import { Button } from "@tremor/react";
import { useWorkflowJsonSchema } from "@/entities/workflows/lib/useWorkflowJsonSchema";
import { KeepLoader } from "../../KeepLoader/KeepLoader";
import { downloadFileFromString } from "@/shared/lib/downloadFileFromString";
import { YamlValidationError } from "../model/types";
import { WorkflowYAMLValidationErrors } from "./WorkflowYAMLValidationErrors";
import clsx from "clsx";
import { validateMustacheVariableNameForYAML } from "@/entities/workflows/lib/validation";
import { parseDocument } from "yaml";
import {
  getCurrentPath,
  parseWorkflowYamlStringToJSON,
} from "@/entities/workflows/lib/yaml-utils";

// NOTE: IT IS IMPORTANT TO IMPORT FROM THE SHARED UI DIRECTORY, because import will be replaced for turbopack
import { MonacoYAMLEditor } from "@/shared/ui";
import { getSeverityString, MarkerSeverity } from "../lib/utils";

const KeepSchemaPath = "file:///workflow-schema.json";
export interface WorkflowYAMLEditorProps {
  workflowYamlString: string;
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

export const WorkflowYAMLEditor = ({
  workflowId,
  workflowYamlString,
  filename = "workflow",
  readOnly = false,
  "data-testid": dataTestId = "yaml-editor",
  onMount,
  onChange,
  onSave,
  onValidationErrors,
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

  // Function to find the current step in the workflow based on the path
  const findStepFromPath = useCallback((path: (string | number)[]) => {
    if (!path || path.length < 3) return null;

    // Look for 'steps' in the path
    const stepsIdx = path.findIndex((p) => p === "steps");
    if (stepsIdx === -1) return null;

    // Check if there's an index after 'steps'
    if (stepsIdx + 1 >= path.length || typeof path[stepsIdx + 1] !== "number")
      return null;

    return {
      stepIndex: path[stepsIdx + 1] as number,
      isInStep: true,
    };
  }, []);

  // Function to validate mustache expressions and apply decorations
  const validateMustacheExpressions = useCallback(() => {
    if (!editorRef.current || !monacoRef.current) {
      return;
    }

    const editor = editorRef.current;
    const monaco = monacoRef.current;
    const model = editor.getModel();

    if (!model) {
      return;
    }

    try {
      const text = model.getValue();
      const yamlDoc = parseDocument(text);
      let workflowDefinition;

      try {
        // Parse the YAML to JSON to get the workflow definition
        workflowDefinition = parseWorkflowYamlStringToJSON(text);
      } catch (e) {
        console.warn("Unable to parse YAML for mustache validation", e);
      }

      const mustacheRegex = /\{\{([^}]+)\}\}/g;
      // Collect markers to add to the model
      const markers: editor.IMarkerData[] = [];

      let match;
      while ((match = mustacheRegex.exec(text)) !== null) {
        const fullMatch = match[0]; // The entire {{...}} expression
        const matchStart = match.index;
        const matchEnd = matchStart + fullMatch.length;

        // Get the position (line, column) for the match
        const startPos = model.getPositionAt(matchStart);
        const endPos = model.getPositionAt(matchEnd);

        // Get the current path in the YAML document
        const path = getCurrentPath(yamlDoc, matchStart);

        // Extract step information from the path
        const stepInfo = findStepFromPath(path);

        let errorMessage: string | null = null;
        let isError = false;
        let severity: "error" | "warning" = "warning";

        // Basic validation that works without full context
        const variableContent = match[1].trim();

        // If we have both the workflow definition and step info, we can do proper validation
        if (
          workflowDefinition &&
          stepInfo &&
          workflowDefinition.workflow &&
          workflowDefinition.workflow.steps
        ) {
          const currentStep =
            workflowDefinition.workflow.steps[stepInfo.stepIndex];

          if (currentStep) {
            // Use the actual validation function from the workflow library
            errorMessage = validateMustacheVariableNameForYAML(
              fullMatch,
              currentStep,
              workflowDefinition.workflow,
              {} // secrets, which you'd need to obtain from somewhere
            );

            isError = !!errorMessage;
            if (isError) {
              severity = "error";
            }
          }
        } else {
          // Fallback to basic validation
          const parts = variableContent.split(".");
          isError = parts.some((part) => !part || part.trim() === "");

          if (isError) {
            errorMessage = `Invalid mustache variable: '${variableContent}' - Parts cannot be empty.`;
            severity = "error";
          }
        }

        // Add decoration for errors
        if (isError && errorMessage) {
          // Add marker for the problems panel and collection
          markers.push({
            severity:
              severity === "error"
                ? MarkerSeverity.Error
                : MarkerSeverity.Warning,
            message: errorMessage,
            startLineNumber: startPos.lineNumber,
            startColumn: startPos.column,
            endLineNumber: endPos.lineNumber,
            endColumn: endPos.column,
            source: "mustache-validation",
          });
        }
        // For valid patterns, add warnings if we couldn't do full validation
        else if (
          !workflowDefinition &&
          (variableContent.startsWith("steps.") ||
            variableContent.startsWith("secrets.") ||
            variableContent.startsWith("alert.") ||
            variableContent.startsWith("incident."))
        ) {
          const warningMessage = `Warning: Unable to fully validate mustache variable '${variableContent}' without complete workflow context.`;

          // Add warning marker
          markers.push({
            severity: MarkerSeverity.Warning,
            message: warningMessage,
            startLineNumber: startPos.lineNumber,
            startColumn: startPos.column,
            endLineNumber: endPos.lineNumber,
            endColumn: endPos.column,
            source: "mustache-validation",
          });
        }
      }

      // Set markers on the model for the problems panel
      monaco.editor.setModelMarkers(model, "mustache-validation", markers);
    } catch (error) {
      console.error("Error validating mustache expressions:", error);
    }
  }, [findStepFromPath]);

  const handleMarkersChanged = (
    modelUri: Uri,
    markers: editor.IMarker[] | editor.IMarkerData[],
    owner: string
  ) => {
    const editorUri = editorRef.current!.getModel()?.uri;
    if (modelUri.path !== editorUri?.path) {
      return;
    }
    const errors: YamlValidationError[] = [];
    for (const marker of markers) {
      if (marker.severity === MarkerSeverity.Hint) {
        continue;
      }
      errors.push({
        message: marker.message,
        severity: getSeverityString(marker.severity),
        lineNumber: marker.startLineNumber,
        column: marker.startColumn,
        owner,
      });
    }
    setValidationErrors((prevErrors) => {
      const prevOtherOwners = prevErrors?.filter((e) => e.owner !== owner);
      return [...(prevOtherOwners ?? []), ...errors];
    });
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
      handleMarkersChanged(model.uri, markers, owner);
    };

    // Run initial mustache validation
    validateMustacheExpressions();

    // Set up a listener for content changes to re-validate mustache expressions
    editor.onDidChangeModelContent(() => {
      validateMustacheExpressions();
    });

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
              value={workflowYamlString}
              onMount={handleEditorDidMount}
              onChange={onChange}
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
    </>
  );
};
