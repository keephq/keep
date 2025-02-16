import Loading from "@/app/(keep)/loading";
import {
  LogEntry,
  WorkflowExecutionDetail,
} from "@/shared/api/workflow-executions";
import { Card } from "@tremor/react";
import clsx from "clsx";
import { useEffect, useMemo, useState } from "react";
import { getLogLineStatus } from "../lib/logs-utils";
import {
  CheckCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ClockIcon,
  XCircleIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/20/solid";
import parseISO from "date-fns/parseISO";
import formatDistance from "date-fns/formatDistance";
import { differenceInSeconds } from "date-fns";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import Editor from "@monaco-editor/react";

function getStepIcon(status: string) {
  switch (status) {
    case "success":
      return <CheckCircleIcon className="text-green-500 size-5" />;
    case "failed":
      return <XCircleIcon className="text-red-500 size-5" />;
    case "skipped":
      return <ExclamationCircleIcon className="text-gray-500 size-5" />;
    case "pending":
      return <ClockIcon className="text-yellow-500 size-5" />;
  }
}

type LogGroup = {
  id: string | null;
  name?: string;
  status: string | null;
  startTime: Date | null;
  endTime: Date | null;
  logs: {
    log: LogEntry;
    result: any;
  }[];
};

function formatStepDuration(startTime: Date | null, endTime: Date | null) {
  if (!startTime || !endTime) {
    return "0s";
  }
  if (differenceInSeconds(endTime, startTime) < 60) {
    return `${differenceInSeconds(endTime, startTime)}s`;
  }
  return formatDistance(endTime, startTime, {
    includeSeconds: false,
    addSuffix: false,
  });
}

function getAccordionHeaderClassName(
  status: string | null,
  isHovered: boolean,
  isOpen: boolean
) {
  switch (status) {
    case "success":
      return clsx(
        "bg-green-100 hover:bg-green-200",
        isHovered && "bg-green-200",
        isOpen && "border-green-200"
      );
    case "failed":
      return clsx(
        "bg-red-100 hover:bg-red-200",
        isHovered && "bg-red-200",
        isOpen && "border-red-200"
      );
    case "pending":
      return clsx(
        "bg-yellow-100 hover:bg-yellow-200",
        isHovered && "bg-yellow-200",
        isOpen && "border-yellow-200"
      );
    case "skipped":
      return clsx(
        "bg-gray-100 hover:bg-gray-200",
        isHovered && "bg-gray-200",
        isOpen && "border-gray-200"
      );
    default:
      return clsx(
        "hover:bg-gray-200",
        isHovered && "bg-gray-200",
        isOpen && "border-gray-200"
      );
  }
}

function getChevronIconClassName(status: string | null) {
  switch (status) {
    case "success":
      return "text-green-600";
    case "failed":
      return "text-red-600";
    case "pending":
      return "text-yellow-600";
    default:
      return "text-gray-600";
  }
}

function getLogLineClassName(log: LogEntry) {
  switch (getLogLineStatus(log)) {
    case "success":
      return "text-green-600";
    case "failed":
      return "text-red-600";
  }
}

function LogGroupAccordion({
  defaultOpen = false,
  group,
  isHovered,
  isSelected,
}: {
  defaultOpen?: boolean;
  group: LogGroup;
  isHovered: boolean;
  isSelected: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  useEffect(() => {
    if (isSelected) {
      setIsOpen(true);
    }
  }, [isSelected]);

  return (
    <div>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          "w-full flex justify-between px-2 py-2 rounded-lg border border-transparent transition-colors",
          getAccordionHeaderClassName(group.status, isHovered, isOpen)
        )}
      >
        <div className="w-full flex items-center justify-between gap-2">
          <span className="flex items-center gap-1 min-w-0">
            {isOpen ? (
              <ChevronDownIcon
                className={clsx(
                  "size-5",
                  getChevronIconClassName(group.status)
                )}
              />
            ) : (
              <ChevronRightIcon
                className={clsx(
                  "size-5",
                  getChevronIconClassName(group.status)
                )}
              />
            )}
            {group.status ? getStepIcon(group.status) : null}
            <span className="whitespace-nowrap overflow-hidden text-ellipsis">
              {group.name}
            </span>
          </span>
          <span className="font-mono text-sm">
            {formatStepDuration(group.startTime, group.endTime)}
          </span>
        </div>
      </button>
      {isOpen && (
        <div className="p-2">
          {group.logs.map(({ log, result }, i) => (
            <div key={log.timestamp + i}>
              <p
                className={clsx("text-sm font-mono", getLogLineClassName(log))}
              >
                {log.timestamp}: {log.message}
              </p>
              {result && (
                <div className="bg-gray-100 rounded-md overflow-hidden text-xs my-2">
                  <div className="text-gray-500 bg-gray-50 p-2 flex justify-between items-center">
                    <span>output</span>
                  </div>
                  <div
                    className="overflow-auto"
                    style={{
                      height: Math.min(
                        JSON.stringify(result, null, 2).split("\n").length * 18,
                        192
                      ),
                    }}
                  >
                    <Editor
                      value={JSON.stringify(result, null, 2)}
                      language="json"
                      theme="vs-light"
                      options={{
                        readOnly: true,
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        fontSize: 12,
                        lineNumbers: "off",
                        folding: true,
                        wordWrap: "on",
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function WorkflowExecutionLogs({
  logs,
  results,
  status,
  checks,
  hoveredStep,
  selectedStep,
}: {
  logs: LogEntry[] | null;
  results: Record<string, any> | null;
  status: WorkflowExecutionDetail["status"];
  checks: number;
  hoveredStep: string | null;
  selectedStep: string | null;
}) {
  const groupedLogs = useMemo(() => {
    if (!logs) {
      return [];
    }

    const groupedLogs: LogGroup[] = [];
    let currentGroup: LogGroup | null = null;
    let currentStepName: string | null = null;

    function createNewGroup(
      id: string | null,
      logMessage: string | undefined,
      timestamp: string
    ): LogGroup {
      const newGroup: LogGroup = {
        id,
        name: logMessage,
        status: null,
        logs: [],
        startTime: parseISO(timestamp),
        endTime: null,
      };

      if (currentGroup) {
        currentGroup.endTime = parseISO(timestamp);
      }

      groupedLogs.push(newGroup);
      return newGroup;
    }

    for (const log of logs) {
      // Check for step start in log message
      const stepStartMatch = log.message?.match(
        /Running (step|action) ([a-zA-Z0-9-_]+)/
      );
      if (stepStartMatch) {
        currentStepName = stepStartMatch[2];
      }

      // Get status and result for the log entry
      const status = getLogLineStatus(log);
      const stepId = log.context?.step_id ?? currentStepName;
      const result =
        status === "success" || (status === "failed" && stepId)
          ? results?.[stepId]
          : null;

      // Initialize first group if needed
      if (!currentGroup) {
        currentGroup = createNewGroup(null, log.message, log.timestamp);
      }

      // Create new group if we're switching context
      if (currentStepName) {
        const messageBelongsToCurrentStep =
          log.message?.includes(currentStepName) ||
          log.context?.step_id === currentStepName;
        const needsNewGroup =
          stepStartMatch || messageBelongsToCurrentStep
            ? currentGroup.id !== currentStepName
            : currentGroup.id !== null;

        if (needsNewGroup) {
          currentGroup = createNewGroup(
            messageBelongsToCurrentStep ? currentStepName : null,
            log.message,
            log.timestamp
          );
        }
      } else if (currentGroup.id !== null) {
        currentGroup = createNewGroup(null, log.message, log.timestamp);
      }

      // Update group status and add log
      if (status) {
        currentGroup.status = status;
      }

      currentGroup.logs.push({ log, result });
    }

    return groupedLogs;
  }, [logs, results]);

  return (
    <Card className="flex flex-col overflow-hidden p-2">
      <div className="flex-1 overflow-auto">
        {status === "in_progress" ? (
          <div>
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="flex gap-2 h-10">
                <div className="w-6 h-6">
                  <Skeleton className="w-full h-6" />
                </div>
                <div className="flex-1">
                  <Skeleton className="w-full h-6" />
                </div>
              </div>
            ))}
            <p>
              The workflow is in progress, will check again in one second (times
              checked: {checks})
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {groupedLogs.map((group, index) => (
              <LogGroupAccordion
                key={group.id ?? "" + index}
                defaultOpen={
                  group.status === "pending" || group.status === "failed"
                }
                group={group}
                isSelected={selectedStep !== null && selectedStep === group.id}
                isHovered={hoveredStep !== null && hoveredStep === group.id}
              />
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
