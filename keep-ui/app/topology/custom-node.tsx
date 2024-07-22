import React from "react";
import { Handle, Position } from "@xyflow/react";

const CustomNode = ({ data }: { data: any }) => {
  return (
    <div className="custom-node">
      <strong>{data.label}</strong>
      <Handle type="target" position={Position.Top} isConnectable={false} />
      <Handle type="source" position={Position.Bottom} isConnectable={false} />
    </div>
  );
};

export default CustomNode;
