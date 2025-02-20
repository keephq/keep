import {
  V2ActionStep,
  V2Step,
  V2StepStep,
  V2StepTrigger,
} from "@/entities/workflows";
import clsx from "clsx";
import Image from "next/image";
import { NodeTriggerIcon } from "@/entities/workflows/ui/NodeTriggerIcon";
import { normalizeStepType } from "../../lib/utils";
import {
  getYamlStepFromStep,
  getYamlActionFromAction,
} from "@/entities/workflows/lib/parser";
import { Editor } from "@monaco-editor/react";
import { stringify } from "yaml";
import { getTriggerDescriptionFromStep } from "@/entities/workflows/lib/getTriggerDescription";

function getStepIconUrl(data: V2Step | V2StepTrigger) {
  const { type } = data || {};
  if (type === "alert" || type === "workflow" || type === "trigger" || !type)
    return "/keep.png";
  if (type === "incident" || type === "workflow" || type === "trigger" || !type)
    return "/keep.png";
  return `/icons/${normalizeStepType(type)}-icon.png`;
}

function getYamlFromStep(step: V2Step | V2StepTrigger) {
  try {
    if (step.componentType === "task" && step.type.startsWith("step-")) {
      return getYamlStepFromStep(step as V2StepStep);
    }
    if (step.componentType === "task" && step.type.startsWith("action-")) {
      return getYamlActionFromAction(step as V2ActionStep);
    }
    if (step.componentType === "trigger") {
      return {
        type: step.type,
        ...step.properties,
      };
    }
    // TODO: add other types
    return null;
  } catch (error) {
    console.error(error);
    return null;
  }
}

export const StepPreview = ({
  step,
  className,
}: {
  step: V2Step | V2StepTrigger;
  className?: string;
}) => {
  const yamlDefinition = getYamlFromStep(step);
  const yaml = yamlDefinition ? stringify(yamlDefinition) : null;

  const displayName = step.name;
  const subtitle = getTriggerDescriptionFromStep(step as V2StepTrigger);

  return (
    <div className="flex flex-col gap-2">
      <div
        className={clsx(
          "max-w-[250px] flex shadow-md bg-white border-2 border-stone-400 px-4 py-2 flex-1 flex-row items-center justify-between gap-2 flex-wrap text-sm",
          step.componentType === "trigger" ? "rounded-full" : "rounded-md",
          className
        )}
      >
        {step.componentType === "trigger" ? (
          <NodeTriggerIcon nodeData={step} />
        ) : (
          <Image
            src={getStepIconUrl(step)}
            alt={step?.type}
            className="object-cover w-8 h-8"
            width={32}
            height={32}
          />
        )}
        <div className="flex-1 flex-col gap-2 flex-wrap truncate">
          <div className="font-bold truncate">{displayName}</div>
          <div className="text-gray-500 truncate">{subtitle}</div>
        </div>
      </div>
      {yaml && (
        <details className="text-sm text-gray-500 overflow-auto bg-[#fffffe] break-words whitespace-pre-wrap border rounded  border-gray-200">
          <summary className="text-gray-500 bg-gray-50 p-2">yaml</summary>
          <div
            className="py-2"
            style={{
              height: Math.min(yaml?.split("\n").length * 20 + 8, 192),
            }}
          >
            <Editor
              value={yaml}
              language="yaml"
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
        </details>
      )}
    </div>
  );
};
