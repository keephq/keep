import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';

function IconUrlProvider({ componentType, type }) {
  if (type === "alert" || type === "workflow") return "/keep.png";
  return `/icons/${type
    ?.replace("step-", "")
    .replace("action-", "")
    .replace("condition-", "")}-icon.png`;
}

function SubFlowNode({ data }) {
  return (
    <div className="px-4 py-2 shadow-md rounded-md bg-white border-2 border-orange-400">
      <div className="flex">
        <div className="rounded-full w-12 h-12 flex justify-center items-center bg-gray-100">
          <img
            src={IconUrlProvider(data)}
            alt={data?.type}
            className='object-cover'
          />
        </div>
        <div className="ml-2">
          <div className="text-lg font-bold">{data?.label}</div>
          <div className="text-gray-500">{data?.componentType}</div>
        </div>
      </div>
      <Handle
        type="target"
        position={Position.Top}
        className="w-16 !bg-teal-500"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="w-16 !bg-teal-500"
      />
    </div>
  );
}

export default memo(SubFlowNode);
