import { LogEntry } from "@/shared/api/workflow-executions";

export function getLogLineStatus(log: LogEntry) {
  const isFailure =
    log.message?.includes("Failed to") || log.message?.includes("Error");
  const isSuccess = log.message?.includes("ran successfully");
  return isFailure ? "failed" : isSuccess ? "success" : null;
}

export function getStepStatus(
  stepName: string,
  isAction: boolean,
  logs: LogEntry[]
) {
  if (!logs) return "pending";

  const type = isAction ? "Action" : "Step";
  const successPattern = `${type} ${stepName} ran successfully`;
  const failurePattern = `Failed to run ${type.toLowerCase()} ${stepName}`;

  const hasSuccessLog = logs.some((log) =>
    log.message?.includes(successPattern)
  );
  const hasFailureLog = logs.some((log) =>
    log.message?.includes(failurePattern)
  );

  if (hasSuccessLog) {
    return "success";
  }
  if (hasFailureLog) {
    return "failed";
  }
  return "pending";
}
