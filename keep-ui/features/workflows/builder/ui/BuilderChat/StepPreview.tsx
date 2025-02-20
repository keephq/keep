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
import { YamlStep, YamlAction } from "@/entities/workflows/model/yaml.types";
import { Editor } from "@monaco-editor/react";
import { stringify } from "yaml";

function getStepIconUrl(data: V2Step | V2StepTrigger) {
  const { type } = data || {};
  if (type === "alert" || type === "workflow" || type === "trigger" || !type)
    return "/keep.png";
  if (type === "incident" || type === "workflow" || type === "trigger" || !type)
    return "/keep.png";
  return `/icons/${normalizeStepType(type)}-icon.png`;
}

export const StepPreview = ({
  step,
  className,
}: {
  step: V2Step | V2StepTrigger;
  className?: string;
}) => {
  const type = normalizeStepType(step?.type);
  let yamlOfStep: YamlStep | YamlAction | null = null;
  if (
    step.componentType === "task" &&
    step.type.startsWith("step-") &&
    "stepParams" in step.properties
  ) {
    try {
      yamlOfStep = getYamlStepFromStep(step as V2StepStep);
    } catch (error) {
      console.error(error);
    }
  }
  if (
    step.componentType === "task" &&
    step.type.startsWith("action-") &&
    "actionParams" in step.properties
  ) {
    try {
      yamlOfStep = getYamlActionFromAction(step as V2ActionStep);
    } catch (error) {
      console.error(error);
    }
  }

  const yaml = yamlOfStep ? stringify(yamlOfStep) : null;

  return (
    <div className="flex flex-col gap-2">
      <div
        className={clsx(
          "max-w-[250px] flex shadow-md rounded-md bg-white border-2 border-stone-400 px-4 py-2 flex-1 flex-row items-center justify-between gap-2 flex-wrap text-sm",
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
          <div className="font-bold truncate">{step.name}</div>
          <div className="text-gray-500 truncate">{type}</div>
        </div>
      </div>
      {yaml && (
        <details className="text-sm text-gray-500 overflow-auto bg-[#fffffe] break-words whitespace-pre-wrap py-2 border rounded  border-gray-200">
          <summary>yaml</summary>
          <div
            style={{
              height: Math.min(yaml?.split("\n").length * 20 + 16, 192),
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
