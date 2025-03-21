import React, { useCallback, useEffect, useRef, useState } from "react";
import { type editor } from "monaco-editor";
import { Download, Copy, Check, Save } from "lucide-react";
import { Button } from "@tremor/react";
import { LogEntry } from "@/shared/api/workflow-executions";
import { getStepStatus } from "@/shared/lib/logs-utils";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
import { getOrderedWorkflowYamlString } from "@/entities/workflows/lib/yaml-utils";
import { MonacoEditor } from "@/shared/ui";
import "./MonacoYAMLEditor.css";
interface Props {
  workflowRaw: string;
  workflowId?: string;
  filename?: string;
  executionLogs?: LogEntry[] | null;
  executionStatus?: string;
  hoveredStep?: string | null;
  setHoveredStep?: (step: string | null) => void;
  selectedStep?: string | null;
  setSelectedStep?: (step: string | null) => void;
  readOnly?: boolean;
  "data-testid"?: string;
}

const MonacoYAMLEditor = ({
  workflowRaw,
  filename = "workflow",
  workflowId,
  executionLogs,
  executionStatus,
  hoveredStep,
  setHoveredStep,
  selectedStep,
  setSelectedStep,
  readOnly = false,
  "data-testid": dataTestId = "yaml-editor",
}: Props) => {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const { updateWorkflow } = useWorkflowActions();

  const findStepNameForPosition = (
    lineNumber: number,
    model: editor.ITextModel
  ): string | null => {
    let currentLine = lineNumber;
    let currentIndent = -1;

    while (currentLine > 0) {
      const line = model.getLineContent(currentLine);
      const indent = line.search(/\S/);
      const trimmedLine = line.trim();

      // If we find a line with less indentation than our current tracking,
      // we've moved out of the current step block
      if (indent !== -1 && (currentIndent === -1 || indent < currentIndent)) {
        const nameMatch = trimmedLine.match(/^- name:\s*(.+)/);
        if (nameMatch) {
          return nameMatch[1].trim();
        }
        currentIndent = indent;
      }

      currentLine--;
    }
    return null;
  };

  const stepDecorationsRef = useRef<string[]>([]);
  const hoverDecorationsRef = useRef<string[]>([]);
  const [isEditorMounted, setIsEditorMounted] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [originalContent, setOriginalContent] = useState("");

  const getStatus = useCallback(
    (name: string, isAction: boolean = false) => {
      if (!executionLogs || !executionStatus) {
        return "pending";
      }
      if (executionStatus === "in_progress") {
        return "in_progress";
      }
      return getStepStatus(name, isAction, executionLogs);
    },
    [executionLogs, executionStatus]
  );

  const handleEditorDidMount = (
    editor: editor.IStandaloneCodeEditor,
    monacoInstance: typeof import("monaco-editor")
  ) => {
    editorRef.current = editor;

    const updateStepDecorations = () => {
      if (!editor) return;

      const model = editor.getModel();
      if (!model) return;

      const content = model.getValue();
      const lines = content.split("\n");
      const decorations: editor.IModelDeltaDecoration[] = [];

      let isInActions = false;
      let currentName: string | null = null;
      let stepStartLine = -1;
      let indentLevel = -1;

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmedLine = line.trim();
        const currentIndent = line.search(/\S/);

        if (trimmedLine === "actions:") {
          isInActions = true;
        } else if (trimmedLine === "steps:") {
          isInActions = false;
        }

        if (trimmedLine.startsWith("- name:")) {
          if (stepStartLine !== -1 && currentName) {
            const status = getStatus(currentName, isInActions);
            decorations.push({
              range: new monacoInstance.Range(stepStartLine + 1, 1, i, 1),
              options: {
                isWholeLine: true,
                className: `workflow-step ${status}`,
              },
            });
          }

          currentName = trimmedLine.split("name:")[1].trim();
          stepStartLine = i;
          indentLevel = currentIndent;

          if (currentName) {
            const status = getStatus(currentName, isInActions);
            decorations.push({
              range: new monacoInstance.Range(i + 1, 1, i + 1, 1),
              options: {
                glyphMarginClassName: `status-indicator ${status}`,
                glyphMarginHoverMessage: { value: `Status: ${status}` },
              },
            });
          }
        } else if (
          currentIndent <= indentLevel &&
          trimmedLine.startsWith("-")
        ) {
          if (stepStartLine !== -1 && currentName) {
            const status = getStatus(currentName, isInActions);
            decorations.push({
              range: new monacoInstance.Range(stepStartLine + 1, 1, i, 1),
              options: {
                isWholeLine: true,
                className: `workflow-step ${status}`,
              },
            });
          }

          currentName = null;
          stepStartLine = -1;
          indentLevel = -1;
        }
      }

      // Handle the last step
      if (stepStartLine !== -1 && currentName) {
        const status = getStatus(currentName, isInActions);
        decorations.push({
          range: new monacoInstance.Range(
            stepStartLine + 1,
            1,
            lines.length,
            1
          ),
          options: {
            isWholeLine: true,
            className: `workflow-step ${status}`,
          },
        });
      }

      stepDecorationsRef.current = editor.deltaDecorations(
        stepDecorationsRef.current,
        decorations
      );
    };

    const updateHoverDecorations = (
      stepNameToHover: string | null | undefined
    ) => {
      if (!editor || !stepNameToHover) return;

      const model = editor.getModel();
      if (!model) return;

      const content = model.getValue();
      const lines = content.split("\n");
      const hoverDecorations: editor.IModelDeltaDecoration[] = [];

      let currentName: string | null = null;
      let stepStartLine = -1;
      let indentLevel = -1;

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmedLine = line.trim();
        const currentIndent = line.search(/\S/);

        if (trimmedLine.startsWith("- name:")) {
          if (currentName === stepNameToHover) {
            const status = getStatus(currentName, false);
            hoverDecorations.push({
              range: new monacoInstance.Range(stepStartLine + 1, 1, i, 1),
              options: {
                isWholeLine: true,
                className: `workflow-step ${status} hovered`,
              },
            });
          }

          currentName = trimmedLine.split("name:")[1].trim();
          stepStartLine = i;
          indentLevel = currentIndent;
        } else if (
          currentIndent <= indentLevel &&
          trimmedLine.startsWith("-")
        ) {
          if (currentName === stepNameToHover) {
            const status = getStatus(currentName, false);

            hoverDecorations.push({
              range: new monacoInstance.Range(stepStartLine + 1, 1, i, 1),
              options: {
                isWholeLine: true,
                className: `workflow-step ${status} hovered`,
              },
            });
          }

          currentName = null;
          stepStartLine = -1;
          indentLevel = -1;
        }
      }

      // Handle the last step
      if (stepStartLine !== -1 && currentName === stepNameToHover) {
        const status = getStatus(currentName, false);
        hoverDecorations.push({
          range: new monacoInstance.Range(
            stepStartLine + 1,
            1,
            lines.length,
            1
          ),
          options: {
            isWholeLine: true,
            className: `workflow-step ${status} hovered`,
          },
        });
      }

      hoverDecorationsRef.current = editor.deltaDecorations(
        hoverDecorationsRef.current,
        hoverDecorations
      );
    };

    if (!readOnly) {
      editor.onDidChangeModelContent(() => {
        const currentContent = editor.getValue();
        setHasChanges(currentContent !== originalContent);
      });
    }

    if (readOnly) {
      // Enable the glyph margin for status indicators
      editor.updateOptions({
        glyphMargin: true,
      });

      // Initial decoration update
      updateStepDecorations();

      // Update step decorations when content changes
      editor.onDidChangeModelContent(() => {
        updateStepDecorations();
        updateHoverDecorations(hoveredStep);
      });

      // Watch for hover step changes and update decorations
      const disposable = editor.onDidChangeModelContent(() => {
        updateStepDecorations();
        updateHoverDecorations(hoveredStep);
      });

      editor.onMouseMove((e) => {
        if (!setHoveredStep) return;

        const target = e.target;
        if (target.type !== monacoInstance.editor.MouseTargetType.CONTENT_TEXT)
          return;

        const position = target.position;
        if (!position) return;

        const model = editor.getModel();
        if (!model) return;

        const stepName = findStepNameForPosition(position.lineNumber, model);
        if (stepName !== hoveredStep) {
          setHoveredStep(stepName);
          updateHoverDecorations(stepName);
        }
      });

      editor.onMouseLeave(() => {
        if (setHoveredStep) {
          setHoveredStep(null);
          // Clear hover decorations
          updateHoverDecorations(null);
        }
      });

      // Handle click for step selection
      editor.onMouseDown((e) => {
        if (!setSelectedStep) return;

        const position = e.target.position;
        if (!position) return;

        const model = editor.getModel();
        if (!model) return;

        let currentLine = position.lineNumber;
        while (currentLine > 0) {
          const line = model.getLineContent(currentLine);
          const match = line.match(/- name:\s*(.+)/);
          if (match) {
            const stepName = match[1].trim();
            // if already selected, deselect
            if (selectedStep === stepName) {
              setSelectedStep(null);
              break;
            }
            setSelectedStep(stepName);
            break;
          }
          currentLine--;
        }
      });

      // Initial update
      updateStepDecorations();

      // Watch for hoveredStep changes
      return () => {
        disposable.dispose();
      };
    }

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

    const content = editorRef.current.getValue();
    try {
      // sending the yaml string to the backend
      // TODO: validate the yaml content and show useful (inline) errors
      await updateWorkflow(workflowId, content);

      setOriginalContent(content);
      setHasChanges(false);
    } catch (err) {
      console.error("Failed to save workflow:", err);
    }
  };

  const downloadYaml = () => {
    if (!editorRef.current) return;
    const content = editorRef.current.getValue();
    const blob = new Blob([content], { type: "text/yaml" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${filename}.yaml`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
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
  };

  return (
    <div
      className="w-full h-full flex flex-col"
      data-testid={dataTestId + "-container"}
    >
      <div
        className="relative flex-1 min-h-0"
        style={{ height: "calc(100vh - 300px)" }}
      >
        <div className="absolute right-2 top-2 z-10 flex gap-2">
          {!readOnly && (
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
        <MonacoEditor
          wrapperProps={{ "data-testid": dataTestId }}
          height="100%"
          defaultLanguage="yaml"
          defaultValue={getOrderedWorkflowYamlString(workflowRaw)}
          onMount={handleEditorDidMount}
          options={editorOptions}
        />
      </div>
      <div className="flex items-center justify-between px-4 py-2 border-t border-gray-200">
        <span className="text-sm text-gray-500">{filename}.yaml</span>
        {workflowId && (
          <span className="text-sm text-gray-500">{workflowId}</span>
        )}
      </div>
    </div>
  );
};

export default MonacoYAMLEditor;
