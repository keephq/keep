import { V2Step, V2StepTrigger } from "@/entities/workflows";
import clsx from "clsx";
import Image from "next/image";
import { NodeTriggerIcon } from "@/entities/workflows/ui/NodeTriggerIcon";
import { normalizeStepType } from "../../builder/lib/utils";
import { stringify } from "yaml";
import { getTriggerDescriptionFromStep } from "@/entities/workflows/lib/getTriggerDescription";
import { getYamlFromStep } from "../lib/utils";
import { WF_DEBUG_INFO } from "../../builder/ui/debug-settings";
import { JsonCard, MonacoEditor } from "@/shared/ui";

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
  const yamlDefinition = getYamlFromStep(step);
  const yaml = yamlDefinition ? stringify(yamlDefinition) : null;

  const displayName = step.name;
  const subtitle = getTriggerDescriptionFromStep(step as V2StepTrigger);

  return (
    <div className="flex flex-col gap-2">
      {WF_DEBUG_INFO && <JsonCard title="step" json={step} />}
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
            <MonacoEditor
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
