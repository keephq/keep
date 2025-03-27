import { YamlValidationErrorSeverity } from "../model/types";

// Copied from monaco-editor/esm/vs/editor/editor.api.d.ts because we can't import with turbopack
export enum MarkerSeverity {
  Hint = 1,
  Info = 2,
  Warning = 4,
  Error = 8,
}

function getSeverityString(
  severity: MarkerSeverity
): YamlValidationErrorSeverity {
  if (severity === MarkerSeverity.Error) {
    return "error";
  }
  if (severity === MarkerSeverity.Warning) {
    return "warning";
  }
  if (severity === MarkerSeverity.Info) {
    return "info";
  }
  return "info";
}

export { getSeverityString };
