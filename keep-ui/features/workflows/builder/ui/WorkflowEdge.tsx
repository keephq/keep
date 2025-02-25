import React from "react";
import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath } from "@xyflow/react";
import type { EdgeProps } from "@xyflow/react";
import { useWorkflowStore } from "@/entities/workflows";
import { Button } from "@tremor/react";
import "@xyflow/react/dist/style.css";
import { PlusIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";
import { WF_DEBUG_INFO } from "./debug-settings";
import { edgeCanHaveAddButton } from "../lib/utils";

export function DebugEdgeInfo({
  id,
  source,
  labelX,
  labelY,
  target,
  isLayouted,
}: Pick<WorkflowEdgeProps, "id" | "source" | "target"> & {
  labelX: number;
  labelY: number;
  isLayouted: boolean;
}) {
  if (!WF_DEBUG_INFO) {
    return null;
  }
  return (
    <div
      className={`absolute bg-black text-green-500 font-mono text-[10px] px-1 py-1`}
      style={{
        transform: `translate(0, -50%) translate(${labelX + 30}px, ${labelY}px)`,
        opacity: isLayouted ? 1 : 0,
        pointerEvents: "all",
      }}
    >
      {id}
      <details>
        <summary>data=</summary>
        <pre>{JSON.stringify({ source, target }, null, 2)}</pre>
      </details>
    </div>
  );
}

export interface WorkflowEdgeProps extends EdgeProps {
  label?: string;
  type?: string;
  data?: any;
}

export const WorkflowEdge: React.FC<WorkflowEdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  label,
  source,
  target,
  data,
  style,
}: WorkflowEdgeProps) => {
  const { setSelectedEdge, selectedEdge } = useWorkflowStore();

  // Calculate the path and midpoint
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    borderRadius: 10,
  });

  let dynamicLabel = label;
  const isLayouted = !!data?.isLayouted;
  let showAddButton = edgeCanHaveAddButton(source, target);

  const color =
    dynamicLabel === "True"
      ? "left-0 bg-green-500"
      : dynamicLabel === "False"
        ? "bg-red-500"
        : "bg-orange-500";

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          opacity: isLayouted ? 1 : 0,
          ...style,
          strokeWidth: 2,
        }}
      />
      <defs>
        <marker
          id={`arrow-${id}`}
          markerWidth="15"
          markerHeight="15"
          refX="10"
          refY="5"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path
            d="M 0,0 L 10,5 L 0,10 L 3,5 Z"
            fill="currentColor"
            className="text-gray-500 font-extrabold" // Tailwind class for arrow color
            style={{ opacity: isLayouted ? 1 : 0 }}
          />
        </marker>
      </defs>
      <BaseEdge
        id={id}
        path={edgePath}
        className="stroke-gray-700 stroke-2"
        style={{
          markerEnd: target !== "end" ? `url(#arrow-${id})` : undefined,
          opacity: isLayouted ? 1 : 0,
        }} // Add arrowhead
      />
      <EdgeLabelRenderer>
        <DebugEdgeInfo
          id={id}
          source={source}
          target={target}
          labelX={labelX}
          labelY={labelY}
          isLayouted={isLayouted}
        />
        {!!dynamicLabel && (
          <div
            className={`absolute ${color} text-white rounded px-3 py-1 border border-gray-700`}
            style={{
              transform: `translate(-50%, -50%) translate(${
                dynamicLabel === "True" ? labelX - 45 : labelX + 48
              }px, ${labelY}px)`,
              pointerEvents: "none",
              opacity: isLayouted ? 1 : 0,
            }}
          >
            {dynamicLabel}
          </div>
        )}
        {showAddButton && (
          <Button
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: "all",
              opacity: isLayouted ? 1 : 0,
            }}
            className={`p-0 m-0 bg-transparent text-transparent border-none`}
            tooltip={source === "trigger_start" ? "Add trigger" : "Add step"}
            onClick={(e) => {
              setSelectedEdge(id);
            }}
            data-testid={
              source === "trigger_start"
                ? "wf-add-trigger-button"
                : "wf-add-step-button"
            }
          >
            <PlusIcon
              className={clsx(
                "size-7 rounded text-sm border text-black",
                selectedEdge === id
                  ? "border-orange-500 bg-orange-50"
                  : "border-gray-700 hover:bg-gray-50 bg-white"
              )}
            />
          </Button>
        )}
      </EdgeLabelRenderer>
    </>
  );
};
