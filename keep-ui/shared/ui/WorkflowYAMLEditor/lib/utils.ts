import { YamlValidationErrorSeverity } from "../model/types";

// Copied from monaco-editor/esm/vs/editor/editor.api.d.ts because we can't import with turbopack
export enum MarkerSeverity {
  Hint = 1,
  Info = 2,
  Warning = 4,
  Error = 8,
}

export function getSeverityString(
  severity: MarkerSeverity
): YamlValidationErrorSeverity {
  switch (severity) {
    case MarkerSeverity.Error:
      return "error";
    case MarkerSeverity.Warning:
      return "warning";
    case MarkerSeverity.Hint:
      return "hint";
    case MarkerSeverity.Info:
    default:
      return "info";
  }
}

// New utility function to handle error click position
export function navigateToErrorPosition(
  editor: import("monaco-editor").editor.IStandaloneCodeEditor,
  lineNumber: number,
  column: number
): void {
  editor.setPosition({
    lineNumber,
    column,
  });
  editor.focus();
  editor.revealLineInCenter(lineNumber);
}
