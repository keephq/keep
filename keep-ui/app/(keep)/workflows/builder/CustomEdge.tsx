import React from "react";
import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath } from "@xyflow/react";
import type { EdgeProps } from "@xyflow/react";
import useStore from "./builder-store";
import { PlusIcon } from "@radix-ui/react-icons";
import { Button } from "@tremor/react";
import "@xyflow/react/dist/style.css";

interface CustomEdgeProps extends EdgeProps {
  label?: string;
  type?: string;
  data?: any;
}

const CustomEdge: React.FC<CustomEdgeProps> = ({
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
}: CustomEdgeProps) => {
  const { setSelectedEdge, selectedEdge } = useStore();

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
  let showAddButton =
    !source?.includes("empty") &&
    !target?.includes("trigger_end") &&
    source !== "start";

  if (!showAddButton) {
    showAddButton =
      target?.includes("trigger_end") && source?.includes("trigger_start");
  }

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
          markerEnd: `url(#arrow-${id})`,
          opacity: isLayouted ? 1 : 0,
        }} // Add arrowhead
      />
      <EdgeLabelRenderer>
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
            // tooltip="Add node"
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
              className={`size-7 hover:text-black rounded text-sm bg-white border text-gray-700 ${
                selectedEdge === id
                  ? "border-2 border-orange-500"
                  : "border-gray-700"
              }`}
            />{" "}
          </Button>
        )}
      </EdgeLabelRenderer>
    </>
  );
};

export default CustomEdge;
