export type YamlValidationErrorSeverity = "error" | "warning" | "info";

export type YamlValidationError = {
  message: string;
  severity: YamlValidationErrorSeverity;
  lineNumber: number;
  column: number;
  owner: string;
};
