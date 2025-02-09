import { LogEntry } from "@/shared/api/workflow-executions";

export function getLogLineStatus(log: LogEntry) {
  const isFailure =
    log.message?.includes("Failed to") || log.message?.includes("Error");

  const isSuccess = log.message?.includes("ran successfully") && (log.message?.startsWith("Action") || (log.message?.startsWith("Step") && !log.message?.startsWith("Steps")));

  const isSkipped = log.message?.includes("evaluated NOT to run");
  return isFailure ? "failed" : isSuccess ? "success" : isSkipped ? "skipped" : null;
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

  const hasSkipLog = logs.some((log) =>
    log.message?.includes(`evaluated NOT to run`)
  );

  if (hasSuccessLog) {
    return "success";
  }
  if (hasFailureLog) {
    return "failed";
  }

  if (hasSkipLog) {
    return "skipped";
  }

  return "pending";
}
