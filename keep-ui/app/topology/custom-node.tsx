import React from "react";
import { Handle, Position } from "@xyflow/react";
import './custom-node.css';

const CustomNode = ({ data }: { data: any }) => {
  return (
    <div className="custom-node">
      <strong>{data.label}</strong>
      <div className="hover-info">
        <p>Display Name: {data.displayName}</p>
        <p>Description: {data.description}</p>
        <p>Team: {data.team}</p>
        <p>Email: {data.email}</p>
      </div>
      <Handle type="target" position={Position.Top} />
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

export default CustomNode;
