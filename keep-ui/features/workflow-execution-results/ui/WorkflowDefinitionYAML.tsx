import React, { useCallback, useMemo } from "react";
import { load, dump } from "js-yaml";
import clsx from "clsx";
import {
  CheckCircleIcon,
  ClockIcon,
  XCircleIcon,
} from "@heroicons/react/20/solid";
import { getStepStatus } from "../lib/logs-utils";
import { LogEntry } from "@/shared/api/workflow-executions";

interface Props {
  workflowRaw: string;
  executionLogs?: LogEntry[] | null;
  executionStatus?: string;
  hoveredStep: string | null;
  setHoveredStep: (step: string | null) => void;
  selectedStep: string | null;
  setSelectedStep: (step: string | null) => void;
}

export function WorkflowDefinitionYAML({
  workflowRaw,
  executionLogs,
  executionStatus,
  hoveredStep,
  setHoveredStep,
  selectedStep,
  setSelectedStep,
}: Props) {
  const reorderWorkflowSections = (yamlString: string) => {
    const content = yamlString.startsWith('"')
      ? JSON.parse(yamlString)
      : yamlString;

    const workflow = load(content) as any;
    const workflowData = workflow.workflow;

    const metadataFields = ["id", "name", "description", "disabled"];
    const sectionOrder = [
      "triggers",
      "consts",
      "owners",
      "services",
      "steps",
      "actions",
    ];

    const orderedWorkflow: any = {
      workflow: {},
    };

    metadataFields.forEach((field) => {
      if (workflowData[field] !== undefined) {
        orderedWorkflow.workflow[field] = workflowData[field];
      }
    });

    sectionOrder.forEach((section) => {
      if (workflowData[section] !== undefined) {
        orderedWorkflow.workflow[section] = workflowData[section];
      }
    });

    return dump(orderedWorkflow, {
      indent: 2,
      lineWidth: -1,
      noRefs: true,
      sortKeys: false,
      quotingType: '"',
    });
  };

  const reorderedWorkflowSections = useMemo(() => {
    return reorderWorkflowSections(workflowRaw);
  }, [workflowRaw]);

  const getStatus = useCallback(
    (name: string, isAction: boolean = false) => {
      if (!executionLogs || !executionStatus) {
        return "pending";
      }
      if (executionStatus === "in_progress") {
        return "in_progress";
      }

      return getStepStatus(name, isAction, executionLogs);
    },
    [executionLogs, executionStatus]
  );

  const getStepIcon = (status: string) => {
    switch (status) {
      case "success":
        return <CheckCircleIcon className="text-green-500 size-4" />;
      case "failed":
        return <XCircleIcon className="text-red-500 size-4" />;
      case "in_progress":
        return <ClockIcon className="text-yellow-500 size-4" />;
      default:
        return null;
    }
  };

  const getStepClassName = (status: string | null, isHovered: boolean) => {
    switch (status) {
      case "success":
        return isHovered ? "bg-green-200" : "bg-green-100";
      case "failed":
        return isHovered ? "bg-red-200" : "bg-red-100";
      default:
        return "";
    }
  };

  const renderYamlWithIcons = () => {
    const lines = reorderedWorkflowSections.split("\n");
    let firstLineOfStep: number | null = null;
    let currentName: string | null = null;
    let previousName: string | null = null;
    let isInActions = false;

    return lines.map((line, index) => {
      let specialLine = false;
      const trimmedLine = line.trim();

      if (trimmedLine === "actions:") {
        isInActions = true;
        specialLine = true;
      } else if (trimmedLine.startsWith("steps:")) {
        isInActions = false;
        specialLine = true;
      }

      if (trimmedLine.startsWith("- name:")) {
        currentName = trimmedLine.split("name:")[1].trim();
        if (previousName !== currentName) {
          firstLineOfStep = null;
        }
        previousName = currentName;
      }

      const stepName = currentName; // stable reference for hover listener
      const status = currentName ? getStatus(currentName, isInActions) : null;
      const icon = status ? getStepIcon(status) : null;

      if (status && !firstLineOfStep) {
        firstLineOfStep = index;
      }

      if (!status || specialLine) {
        firstLineOfStep = null;
      }

      return (
        <div
          key={index}
          className={clsx(
            "font-mono flex items-center gap-2 px-4 transition-colors",
            getStepClassName(status, hoveredStep === stepName)
          )}
          onMouseEnter={() => setHoveredStep(stepName)}
          onMouseLeave={() => setHoveredStep(null)}
          onClick={() => {
            setSelectedStep(stepName);
            setTimeout(() => {
              setSelectedStep(null);
            }, 100);
          }}
        >
          <div className="w-4 flex items-center">
            {firstLineOfStep === index ? icon : null}
          </div>
          <div className="whitespace-pre-wrap break-all">
            {line || "\u00A0"}
          </div>
        </div>
      );
    });
  };

  return (
    <div className="overflow-auto font-mono text-sm pt-2">
      {renderYamlWithIcons()}
    </div>
  );
}
