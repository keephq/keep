import { V2Step, V2StepTrigger } from "@/entities/workflows";
import clsx from "clsx";
import Image from "next/image";
import { NodeTriggerIcon } from "@/entities/workflows/ui/NodeTriggerIcon";

function getStepIcon(data: V2Step | V2StepTrigger) {
  const { type } = data || {};
  if (type === "alert" || type === "workflow" || type === "trigger" || !type)
    return "/keep.png";
  if (type === "incident" || type === "workflow" || type === "trigger" || !type)
    return "/keep.png";
  return `/icons/${type
    ?.replace("step-", "")
    ?.replace("action-", "")
    ?.replace("__end", "")
    ?.replace("condition-", "")}-icon.png`;
}

export const StepPreview = ({
  step,
  className,
}: {
  step: V2Step | V2StepTrigger;
  className?: string;
}) => {
  const type = step?.type
    ?.replace("step-", "")
    ?.replace("action-", "")
    ?.replace("condition-", "")
    ?.replace("__end", "")
    ?.replace("trigger_", "");

  return (
    <div
      className={clsx(
        "max-w-[250px] flex shadow-md rounded-md bg-white border-2 border-stone-400 p-2 flex-1 flex-row items-center justify-between gap-2 flex-wrap text-sm",
        className
      )}
    >
      {step.componentType === "trigger" ? (
        <NodeTriggerIcon nodeData={step} />
      ) : (
        <Image
          src={getStepIcon(step)}
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
  );
};
