import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import NodeMenu from "./NodeMenu";
import useStore, { FlowNode } from "./builder-store";
import Image from "next/image";


function IconUrlProvider(data: Partial<FlowNode["data"]>) {
  const { componentType, type } = data;
  if (type === "alert" || type === "workflow") return "/keep.png";
  return `/icons/${type
    .replace("step-", "")
    .replace("action-", "")
    .replace("condition-", "")}-icon.png`;
}

function CustomNode({ data, id}:{data: Partial<FlowNode["data"]>}) {
  console.log("entering this CustomNode", data, id);
  const { getNodeById } = useStore();
  const currentNode = getNodeById(id);

  return (
    <>
      {!!currentNode && (
        <div className="p-2  py-4 shadow-md rounded-md bg-white border-2 border-stone-400 w-full h-full">
          {data?.type !== "sub_flow" && (
            <div className="flex  items-start justify-between gap-2">
              <div className="rounded-full w-12 h-12 flex justify-center items-center bg-gray-100">
                <Image
                  src={IconUrlProvider(data) || '/keep.png'}
                  alt={data?.type}
                  className="object-cover w-8 h-8"
                  width={32}
                  height={32}
                />
              </div>
              <div className="flex-1 mr-8">
                <div className="text-lg font-bold">{data?.name}</div>
                <div className="text-gray-500">{data?.componentType}</div>
              </div>
              <div> 
                 <NodeMenu node={currentNode} />
             </div>
            </div>
            
          )}

          <Handle
            type="target"
            position={Position.Top}
            className="!bg-teal-500"
          />
          <Handle
            type="source"
            position={Position.Bottom}
            className="!bg-teal-500"
          />
        </div>
      )}
    </>
  );
}

export default memo(CustomNode);
