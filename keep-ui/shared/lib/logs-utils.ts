import { LogEntry } from "@/shared/api/workflow-executions";

/**
 * Determines the status of a workflow log entry based on its message content
 * 
 * @param log - The log entry to analyze
 * @returns The status string ("failed", "success", "skipped") or null if status cannot be determined
 * 
 * Status is determined by analyzing the log message for specific patterns:
 * - "Failed to" or "Error" indicates failure
 * - "ran successfully" with "Action" or "Step" prefix indicates success
 * - "evaluated NOT to run" indicates skipped
 */
export function getLogLineStatus(log: LogEntry) {
  const isFailure =
    log.message?.includes("Failed to") || log.message?.includes("Error");

  const isSuccess = log.message?.includes("ran successfully") && (log.message?.startsWith("Action") || (log.message?.startsWith("Step") && !log.message?.startsWith("Steps")));

  const isSkipped = log.message?.includes("evaluated NOT to run");
  return isFailure ? "failed" : isSuccess ? "success" : isSkipped ? "skipped" : null;
}

/**
 * Determines the execution status of a workflow step based on the log entries
 * 
 * @param stepName - The name of the step to check
 * @param isAction - Whether the step is an action (true) or a regular step (false)
 * @param logs - Array of log entries to analyze
 * @returns Status string: "success", "failed", "skipped", or "pending"
 * 
 * The function searches log messages for specific patterns related to the step name
 * and determines status based on the presence of success, failure, or skip messages.
 * If no relevant logs are found, the status is considered "pending".
 */
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
