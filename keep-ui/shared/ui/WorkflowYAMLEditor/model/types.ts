import type { editor } from "monaco-editor";

export type YamlValidationErrorSeverity = "error" | "warning" | "info" | "hint";

export type YamlValidationError = {
  message: string;
  severity: YamlValidationErrorSeverity;
  lineNumber: number;
  column: number;
  owner: string;
};

export interface BaseWorkflowYAMLEditorProps {
  workflowId?: string;
  filename?: string;
  readOnly?: boolean;
  "data-testid"?: string;
  onMount?: (
    editor: editor.IStandaloneCodeEditor,
    monacoInstance: typeof import("monaco-editor")
  ) => void;
  onChange?: (value: string | undefined) => void;
  onValidationErrors?: React.Dispatch<
    React.SetStateAction<YamlValidationError[]>
  >;
  onSave?: (value: string) => void;
}

export type WorkflowYAMLEditorDefaultProps = BaseWorkflowYAMLEditorProps & {
  value: string;
};

export type WorkflowYAMLEditorDiffProps = BaseWorkflowYAMLEditorProps & {
  original: string;
  modified: string;
};

export type WorkflowYAMLEditorProps =
  | WorkflowYAMLEditorDefaultProps
  | WorkflowYAMLEditorDiffProps;
