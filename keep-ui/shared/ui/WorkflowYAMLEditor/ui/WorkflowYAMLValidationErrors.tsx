import { Loader2Icon } from "lucide-react";
import { YamlValidationError } from "../types";
import {
  CheckCircleIcon,
  InformationCircleIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/20/solid";
import clsx from "clsx";

export function WorkflowYAMLValidationErrors({
  isMounted,
  validationErrors,
  onErrorClick,
}: {
  isMounted: boolean;
  validationErrors: YamlValidationError[] | null;
  onErrorClick?: (error: YamlValidationError) => void;
}) {
  if (!isMounted) {
    return (
      <div className="bg-gray-100 text-sm flex items-start gap-1 px-4 py-1 z-10 border-t border-gray-200">
        <Loader2Icon className="h-4 w-4 animate-spin shrink-0 mt-0.5" />
        Loading editor...
      </div>
    );
  }
  if (!validationErrors) {
    return (
      <div className="bg-gray-100 text-sm flex items-start gap-1 px-4 py-1 z-10 border-t border-gray-200">
        <Loader2Icon className="h-4 w-4 animate-spin shrink-0 mt-0.5" />
        Initializing validation...
      </div>
    );
  }
  const highestSeverity = validationErrors.reduce(
    (acc: string | null, error) => {
      if (error.severity === "error") return "error";
      if (error.severity === "warning" && acc !== "error") return "warning";
      return acc;
    },
    null
  );
  if (validationErrors.length === 0) {
    return (
      <div className="bg-white text-sm flex items-start gap-1 px-4 py-1 z-10 border-t border-gray-200">
        <CheckCircleIcon className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
        No validation errors
      </div>
    );
  }
  return (
    <details
      className={clsx(
        "border-t border-gray-200 z-10",
        highestSeverity === "info" && "bg-blue-100",
        highestSeverity === "warning" && "bg-yellow-100",
        highestSeverity === "error" && "bg-red-100"
      )}
      open
    >
      <summary className="text-sm cursor-pointer hover:underline gap-1 px-4 py-1">
        {`${validationErrors.length} validation ${
          validationErrors.length === 1 ? "error" : "errors"
        }`}
      </summary>
      <div className="flex flex-col">
        {validationErrors.map((error) => (
          <div
            key={`${error.lineNumber}-${error.column}-${error.message}`}
            className={clsx(
              "text-sm cursor-pointer hover:underline flex items-start gap-1 px-4 py-1",
              error.severity === "error" ? "bg-red-100" : "bg-yellow-100"
            )}
            onClick={() => onErrorClick?.(error)}
          >
            {error.severity === "error" ? (
              <ExclamationCircleIcon className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
            ) : error.severity === "warning" ? (
              <ExclamationTriangleIcon className="h-4 w-4 text-yellow-500 shrink-0 mt-0.5" />
            ) : (
              <InformationCircleIcon className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
            )}
            <span className="text-sm">
              {error.lineNumber}:{error.column} {error.message}
            </span>
          </div>
        ))}
      </div>
    </details>
  );
}
