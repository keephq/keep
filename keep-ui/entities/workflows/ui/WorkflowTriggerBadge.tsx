import { Trigger } from "@/shared/api/workflows";
import { TriggerIcon } from "./TriggerIcon";
import clsx from "clsx";
import { Tooltip } from "@/shared/ui";

export function WorkflowTriggerBadge({
  trigger,
  onClick,
}: {
  trigger: Trigger;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
}) {
  const btn = (
    <button
      className={clsx(
        "border bg-white border-gray-500 p-0.5 pr-2.5 pl-1.5 text-black placeholder-opacity-100 text-xs rounded-3xl font-medium capitalize flex items-center gap-1",
        onClick !== undefined
          ? "hover:bg-gray-100 hover:border-gray cursor-pointer"
          : "hover:bg-white hover:border-gray-500 cursor-default"
      )}
      onClick={onClick}
      disabled={onClick === undefined}
    >
      <TriggerIcon trigger={trigger} />
      {trigger.type}
    </button>
  );

  let tooltipContent = trigger.type;
  switch (trigger.type) {
    case "interval":
      tooltipContent = `Interval: ${trigger.value} seconds`;
      break;
    case "alert":
      tooltipContent = `Source: ${
        trigger.filters?.find((f) => f.key === "source")?.value
      }`;
  }

  return <Tooltip content={tooltipContent}>{btn}</Tooltip>;
}
