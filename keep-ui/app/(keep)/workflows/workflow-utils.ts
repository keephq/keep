import { differenceInSeconds } from "date-fns";
import { LastWorkflowExecution } from "@/shared/api/workflows";

export const getLabels = (lastExecutions: LastWorkflowExecution[]) => {
  if (!lastExecutions || (lastExecutions && lastExecutions.length === 0)) {
    return [];
  }
  return lastExecutions?.map((workflowExecution) => {
    let started = workflowExecution?.started
      ? new Date(workflowExecution?.started + "Z").toLocaleString()
      : "N/A";
    return `${started}(${workflowExecution.status})`;
  });
};

export const getDataValues = (lastExecutions: LastWorkflowExecution[]) => {
  if (!lastExecutions || (lastExecutions && lastExecutions.length === 0)) {
    return [];
  }
  return lastExecutions?.map((workflowExecution) => {
    if (
      workflowExecution?.execution_time === undefined ||
      workflowExecution?.execution_time === null
    ) {
      return differenceInSeconds(
        new Date(Date.now().toLocaleString()),
        new Date(new Date(workflowExecution?.started + "Z").toLocaleString())
      );
    }
    // If the execution time is 0s, return 0.01 to avoid empty graph bars
    // TODO: either update the backend to return float, milliseconds or decide it's not important
    if (workflowExecution.execution_time === 0) {
      return 0.01;
    }
    return workflowExecution.execution_time;
  });
};

const _getColor = (status: string, opacity: number) => {
  if (status === "success") {
    return `rgba(34, 197, 94, ${opacity})`;
  }
  if (["failed", "faliure", "fail", "error"].includes(status)) {
    return `rgba(255, 99, 132, ${opacity})`;
  }

  return `rgba(128, 128, 128, 0.2)`;
};

export const getColors = (
  lastExecutions: LastWorkflowExecution[],
  status: string,
  isBgColor?: boolean
) => {
  const opacity = isBgColor ? 0.2 : 1;
  if (!lastExecutions || (lastExecutions && lastExecutions.length === 0)) {
    return [];
  }
  return lastExecutions?.map((workflowExecution) => {
    const status = workflowExecution?.status?.toLowerCase();
    return _getColor(status, opacity);
  });
};

export function getRandomStatus() {
  const statuses = [
    "success",
    "error",
    "in_progress",
    "timeout",
    "providers_not_configured",
  ];
  return statuses[Math.floor(Math.random() * statuses.length)];
}
