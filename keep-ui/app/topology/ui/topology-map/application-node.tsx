import { NodeProps } from "@xyflow/react";
import { cn } from "utils/helpers";

export function ApplicationNode({ data, selected }: NodeProps) {
  return (
    <div
      className={cn(
        "h-full flex items-start p-2 justify-center rounded-xl bg-green-500/20 border-2 border-green-500/60 -z-10",
        selected ? "border-green-500/60" : "border-green-500/20"
      )}
    >
      <p className="text-lg font-bold text-gray-800">{data?.label as string}</p>
    </div>
  );
}
