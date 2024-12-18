import React from "react";
import { load, dump } from "js-yaml";
import { CheckCircle, XCircle, Clock } from "lucide-react";

interface LogEntry {
  timestamp: string;
  message: string;
}

interface Props {
  workflowRaw: string;
  executionLogs?: LogEntry[] | null;
  executionStatus?: string;
}

export default function WorkflowDefinitionYAML({
  workflowRaw,
  executionLogs,
  executionStatus,
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

  const getStatus = (name: string, isAction: boolean = false) => {
    if (!executionLogs || !executionStatus) return "pending";
    if (executionStatus === "in_progress") return "in_progress";

    const type = isAction ? "Action" : "Step";
    const successPattern = `${type} ${name} ran successfully`;
    const failurePattern = `Failed to run ${type.toLowerCase()} ${name}`;

    const hasSuccessLog = executionLogs.some(
      (log) => log.message?.includes(successPattern)
    );
    const hasFailureLog = executionLogs.some(
      (log) => log.message?.includes(failurePattern)
    );

    if (hasSuccessLog) return "success";
    if (hasFailureLog) return "failed";
    return "pending";
  };

  const getStepIcon = (status: string) => {
    switch (status) {
      case "success":
        return <CheckCircle className="text-green-500" size={16} />;
      case "failed":
        return <XCircle className="text-red-500" size={16} />;
      case "in_progress":
        return <Clock className="text-yellow-500" size={16} />;
      default:
        return null;
    }
  };

  const renderYamlWithIcons = () => {
    const orderedYaml = reorderWorkflowSections(workflowRaw);
    const lines = orderedYaml.split("\n");
    let currentName: string | null = null;
    let isInActions = false;

    return lines.map((line, index) => {
      const trimmedLine = line.trim();

      if (trimmedLine === "actions:") {
        isInActions = true;
      } else if (trimmedLine.startsWith("steps:")) {
        isInActions = false;
      }

      if (trimmedLine.startsWith("- name:")) {
        currentName = trimmedLine.split("name:")[1].trim();
      }

      const status = currentName ? getStatus(currentName, isInActions) : null;
      const icon = status ? getStepIcon(status) : null;

      return (
        <div
          key={index}
          className="font-mono whitespace-pre flex items-center gap-2"
        >
          <div className="w-4 flex items-center">{icon}</div>
          <div>{line || "\u00A0"}</div>
        </div>
      );
    });
  };

  return (
    <div className="overflow-auto font-mono text-sm">
      {renderYamlWithIcons()}
    </div>
  );
}
