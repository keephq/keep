import { V2Step } from "@/entities/workflows";
import { CursorArrowRaysIcon } from "@heroicons/react/20/solid";
import { PiDiamondsFourFill } from "react-icons/pi";
import clsx from "clsx";
import Image from "next/image";

function getStepIcon(data: V2Step) {
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
  step: V2Step;
  className?: string;
}) => {
  const type = step?.type
    ?.replace("step-", "")
    ?.replace("action-", "")
    ?.replace("condition-", "")
    ?.replace("__end", "")
    ?.replace("trigger_", "");

  function getTriggerIcon(step: any) {
    const { type } = step;
    switch (type) {
      case "manual":
        return <CursorArrowRaysIcon className="size-8" />;
      case "interval":
        return <PiDiamondsFourFill size={32} />;
    }
  }
  return (
    <div
      className={clsx(
        "max-w-[250px] flex shadow-md rounded-md bg-white border-2 border-stone-400 p-2 flex-1 flex-row items-center justify-between gap-2 flex-wrap",
        className
      )}
    >
      {getTriggerIcon(step)}
      {!!type && !["interval", "manual"].includes(type) && (
        <Image
          src={getStepIcon(step)}
          alt={step?.type}
          className="object-cover w-8 h-8 rounded-full bg-gray-100"
          width={32}
          height={32}
        />
      )}
      <div className="flex-1 flex-col gap-2 flex-wrap truncate">
        <div className="text-lg font-bold truncate">{step.name}</div>
        <div className="text-gray-500 truncate">{type}</div>
      </div>
    </div>
  );
};
