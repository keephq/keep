import React from 'react';
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  useReactFlow,
} from '@xyflow/react';

interface CustomEdgeProps {
  id: string;
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  label?: string;
}

const CustomEdge: React.FC<CustomEdgeProps> = ({ id, sourceX, sourceY, targetX, targetY, label }) => {
  const { setEdges } = useReactFlow(); Provider

  // Calculate the path and midpoint
  const [edgePath] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    borderRadius: 10,
  });

  const midpointX = (sourceX + targetX) / 2;
  const midpointY = (sourceY + targetY) / 2;

  return (
    <>
      <BaseEdge id={id} path={edgePath} />
      <EdgeLabelRenderer>
        {!!label && (
          <div
            className="absolute bg-orange-500 text-white rounded px-3 py-1 border border-orange-300"
            style={{
              transform: `translate(${midpointX}px, ${midpointY}px)`,
              pointerEvents: 'none',
            }}
          >
            {label}
          </div>
        )}
        <button
          className="absolute bg-red-500 text-white rounded px-2 py-1 hover:bg-red-700"
          style={{
            transform: `translate(${midpointX}px, ${midpointY + 20}px)`,
          }}
          onClick={(e) => {
            e.stopPropagation();
            console.log("Deleting edge with id:", id); // Debugging statement
            setEdges((eds) => eds.filter((e) => e.id !== id));
          }}
        >
          delete
        </button>
      </EdgeLabelRenderer>
    </>
  );
};

export default CustomEdge;
