import { Trigger } from "@/shared/api/workflows";
import { TriggerIcon } from "./TriggerIcon";
import clsx from "clsx";
import { Tooltip } from "@/shared/ui";
import { getTriggerDescription } from "../lib/getTriggerDescription";

export function WorkflowTriggerBadge({
  trigger,
  onClick,
}: {
  trigger: Trigger;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
}) {
  let label = trigger.type;
  let tooltipContent = getTriggerDescription(trigger);

  return (
    <Tooltip content={tooltipContent}>
      <button
        className={clsx(
          "border bg-white border-gray-500 p-0.5 pr-2.5 pl-1.5 text-black placeholder-opacity-100 text-xs rounded-3xl font-medium flex items-center gap-1 capitalize",
          onClick !== undefined
            ? "hover:bg-gray-100 hover:border-gray cursor-pointer"
            : "hover:bg-white hover:border-gray-500 cursor-default"
        )}
        onClick={onClick}
        disabled={onClick === undefined}
      >
        <TriggerIcon trigger={trigger} />
        {label}
      </button>
    </Tooltip>
  );
}
