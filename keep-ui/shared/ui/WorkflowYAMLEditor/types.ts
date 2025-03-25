export type YamlValidationError = {
  message: string;
  severity: "error" | "warning" | "info";
  lineNumber: number;
  column: number;
};
