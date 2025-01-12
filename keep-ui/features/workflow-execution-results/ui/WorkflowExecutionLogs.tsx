import Loading from "@/app/(keep)/loading";
import { WorkflowExecution } from "@/app/(keep)/workflows/builder/types";
import {
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
} from "@tremor/react";
import clsx from "clsx";
import { useMemo } from "react";
import { LogEntry } from "../model/types";
type LogRowProps = (LogMessageRowProps | LogHeaderRowProps) & {
  hoveredStep: string | null;
  setHoveredStep: (step: string | null) => void;
};

type LogMessageRowProps = {
  log: LogEntry;
  result?: Record<string, any>;
  isHeader: false;
  stepName: string;
  isSuccess: boolean;
  isFailure: boolean;
};

type LogHeaderRowProps = {
  isHeader: true;
  stepName: string;
};

function LogRow(props: LogRowProps) {
  if (props.isHeader) {
    return (
      <TableRow
        className={clsx(
          "transition-opacity",
          props.hoveredStep !== null
            ? props.hoveredStep === props.stepName
              ? "opacity-100"
              : "opacity-50"
            : "opacity-100"
        )}
      >
        <TableCell className="whitespace-normal p-1" />
        <TableCell className="whitespace-normal p-1 font-bold">
          {props.stepName}
        </TableCell>
      </TableRow>
    );
  }
  const { log, result, isSuccess, isFailure } = props;
  return (
    <TableRow
      className={clsx(
        "transition-opacity",
        isSuccess && "bg-green-100",
        isFailure && "bg-red-100",
        props.hoveredStep !== null
          ? props.hoveredStep === props.stepName
            ? "opacity-100"
            : "opacity-50"
          : "opacity-100"
      )}
    >
      <TableCell className="align-top whitespace-nowrap text-gray-500 p-1">
        {log.timestamp}
      </TableCell>
      <TableCell className="break-words whitespace-normal p-1">
        {log.message}
        {result && Object.keys(result).length > 0 && (
          <pre className="overflow-auto max-h-48 bg-white rounded-md text-xs mt-2">
            <div className="text-gray-500 bg-gray-50 p-2">result</div>
            <div className="p-2">{JSON.stringify(result, null, 2)}</div>
          </pre>
        )}
      </TableCell>
    </TableRow>
  );
}

export function WorkflowExecutionLogs({
  logs,
  results,
  status,
  checks,
  hoveredStep,
}: {
  logs: LogEntry[] | null;
  results: Record<string, any> | null;
  status: WorkflowExecution["status"];
  checks: number;
  hoveredStep: string | null;
}) {
  const enrichedLogs = useMemo(() => {
    if (!logs) {
      return [];
    }
    const resultedLogs = [];
    let stepName = "";
    for (const log of logs) {
      const stepNameMatch = log.message?.match(
        /Running (step|action) ([a-zA-Z0-9-_]+)/
      );
      const isOpeningStep = stepNameMatch !== null;
      const isSuccess =
        log.message?.includes("evaluated to run") ||
        log.message?.includes("ran successfully");
      const isFailure =
        log.message?.includes("NOT to run") || log.message?.includes("Failed");
      const isFinalStepLog = log.message?.includes("ran successfully");
      const result = isFinalStepLog ? results?.[log.context?.step_id] : null;
      if (stepNameMatch) {
        stepName = stepNameMatch[2];
      }
      if (isOpeningStep) {
        resultedLogs.push({ isHeader: true, stepName });
      }
      resultedLogs.push({
        log,
        isHeader: false,
        result,
        stepName,
        isSuccess,
        isFailure,
      });
    }
    return resultedLogs;
  }, [logs, results]);

  return (
    <Card className="flex flex-col overflow-hidden p-0">
      <div className="flex-1 overflow-auto">
        {status === "in_progress" ? (
          <div>
            <div className="flex items-center justify-center">
              <p>
                The workflow is in progress, will check again in one second
                (times checked: {checks})
              </p>
            </div>
            <Loading />
          </div>
        ) : (
          <div>
            <Table className="w-full">
              <TableHead>
                <TableRow className="border-b border-gray-200 font-bold">
                  <TableCell className="whitespace-normal p-1">
                    Timestamp
                  </TableCell>
                  <TableCell className="break-words whitespace-normal p-1">
                    Message
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {enrichedLogs.map((row, index) => (
                  <LogRow key={index} hoveredStep={hoveredStep} {...row} />
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </Card>
  );
}
