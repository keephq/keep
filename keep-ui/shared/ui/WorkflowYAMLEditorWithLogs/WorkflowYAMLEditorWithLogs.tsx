"use client";
import { LogEntry } from "@/shared/api/workflow-executions";
import { type editor } from "monaco-editor";
import {
  WorkflowYAMLEditor,
  WorkflowYAMLEditorProps,
} from "../WorkflowYAMLEditor/ui/WorkflowYAMLEditor";
import { useCallback, useEffect, useRef } from "react";
import { getStepStatus } from "@/shared/lib/logs-utils";
import "./WorkflowYAMLEditorWithLogs.css";

interface WorkflowYAMLEditorWithLogsProps extends WorkflowYAMLEditorProps {
  executionLogs: LogEntry[] | null | undefined;
  executionStatus: string | null | undefined;
  hoveredStep: string | null | undefined;
  setHoveredStep: (step: string | null) => void;
  selectedStep: string | null | undefined;
  setSelectedStep: (step: string | null) => void;
}

export function WorkflowYAMLEditorWithLogs({
  executionLogs,
  executionStatus,
  hoveredStep,
  setHoveredStep,
  selectedStep,
  setSelectedStep,
  ...props
}: WorkflowYAMLEditorWithLogsProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<typeof import("monaco-editor") | null>(null);
  const stepDecorationsRef = useRef<string[]>([]);
  const hoverDecorationsRef = useRef<string[]>([]);

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

  const updateStepDecorations = useCallback(() => {
    if (!editorRef.current || !monacoRef.current) {
      return;
    }

    const model = editorRef.current.getModel();
    if (!model) {
      return;
    }

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
            range: new monacoRef.current.Range(stepStartLine + 1, 1, i, 1),
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
            range: new monacoRef.current.Range(i + 1, 1, i + 1, 1),
            options: {
              glyphMarginClassName: `status-indicator ${status}`,
              glyphMarginHoverMessage: { value: `Status: ${status}` },
            },
          });
        }
      } else if (currentIndent <= indentLevel && trimmedLine.startsWith("-")) {
        if (stepStartLine !== -1 && currentName) {
          const status = getStatus(currentName, isInActions);
          decorations.push({
            range: new monacoRef.current.Range(stepStartLine + 1, 1, i, 1),
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
        range: new monacoRef.current.Range(
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

    stepDecorationsRef.current = editorRef.current.deltaDecorations(
      stepDecorationsRef.current,
      decorations
    );
  }, [getStatus]);

  const updateHoverDecorations = useCallback(
    (stepNameToHover: string | null | undefined) => {
      if (!editorRef.current || !monacoRef.current || !stepNameToHover) {
        return;
      }

      const model = editorRef.current.getModel();
      if (!model) {
        return;
      }

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
              range: new monacoRef.current.Range(stepStartLine + 1, 1, i, 1),
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
              range: new monacoRef.current.Range(stepStartLine + 1, 1, i, 1),
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
          range: new monacoRef.current.Range(
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

      hoverDecorationsRef.current = editorRef.current.deltaDecorations(
        hoverDecorationsRef.current,
        hoverDecorations
      );
    },
    [getStatus]
  );

  const handleEditorDidMount = (
    editor: editor.IStandaloneCodeEditor,
    monacoInstance: typeof import("monaco-editor")
  ) => {
    editorRef.current = editor;
    monacoRef.current = monacoInstance;

    // Enable the glyph margin for status indicators
    editor.updateOptions({
      glyphMargin: true,
    });

    // Initial decoration update
    updateStepDecorations();

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
      if (!setSelectedStep) {
        return;
      }

      const position = e.target.position;
      if (!position) {
        return;
      }

      const model = editor.getModel();
      if (!model) {
        return;
      }

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

    return () => {
      disposable.dispose();
    };
  };

  useEffect(() => {
    if (executionLogs && executionStatus) {
      updateStepDecorations();
      updateHoverDecorations(null);
    }
  }, [executionLogs, executionStatus]);

  return <WorkflowYAMLEditor onDidMount={handleEditorDidMount} {...props} />;
}
