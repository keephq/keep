import { Handle, NodeProps, Position } from "@xyflow/react";
import { cn } from "../../../../../utils/helpers";
import React from "react";

export const generatePastelColorFromUUID = (
  id: string,
  scale: number = 0.7,
  opacity: number = 0.5,
  tint: number = 0 // New parameter, 0 means no tinting, 1 means full white
) => {
  const hex = id.replace(/-/g, "").slice(0, 6);
  const r = Math.min(
    255,
    Math.round(parseInt(hex.slice(0, 2), 16) * scale + 64)
  );
  const g = Math.min(
    255,
    Math.round(parseInt(hex.slice(2, 4), 16) * scale + 64)
  );
  const b = Math.min(
    255,
    Math.round(parseInt(hex.slice(4, 6), 16) * scale + 64)
  );

  // Blend with white based on tint value
  const tintedR = Math.round(r + (255 - r) * tint);
  const tintedG = Math.round(g + (255 - g) * tint);
  const tintedB = Math.round(b + (255 - b) * tint);

  return `rgba(${tintedR}, ${tintedG}, ${tintedB}, ${opacity})`;
};

export function ApplicationNode({ id, data, selected }: NodeProps) {
  const color = generatePastelColorFromUUID(id, 0.7, 0.2);
  const borderColor = generatePastelColorFromUUID(id, 1, 0.6);
  return (
    <div
      className={cn(
        `h-full flex items-start p-2 justify-center rounded-xl bg-${color}-500/20 border-2 border-${color}-500/60 -z-10`,
        selected ? `border-${color}-500/60` : `border-${color}-500/20`
      )}
      style={{
        backgroundColor: color,
        borderColor: borderColor,
      }}
    >
      <p className="text-lg font-bold text-gray-800">{data?.label as string}</p>
      <Handle type="source" position={Position.Right} id="right" />
      <Handle type="target" position={Position.Left} id="left" />
    </div>
  );
}
