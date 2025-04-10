export type YamlValidationErrorSeverity = "error" | "warning" | "info" | "hint";

export type YamlValidationError = {
  message: string;
  severity: YamlValidationErrorSeverity;
  lineNumber: number;
  column: number;
  owner: string;
};
