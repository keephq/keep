import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import NodeMenu from "./NodeMenu";
import { useWorkflowStore } from "@/entities/workflows";
import Image from "next/image";
import { GoPlus } from "react-icons/go";
import { MdNotStarted } from "react-icons/md";
import { GoSquareFill } from "react-icons/go";
import { PiSquareLogoFill } from "react-icons/pi";
import { toast } from "react-toastify";
import { FlowNode } from "@/entities/workflows/model/types";
import { DynamicImageProviderIcon } from "@/components/ui";
import clsx from "clsx";
import { WF_DEBUG_INFO } from "./debug-settings";
import { ExclamationCircleIcon } from "@heroicons/react/20/solid";
import { Tooltip } from "@/shared/ui/Tooltip";
import { NodeTriggerIcon } from "@/entities/workflows/ui/NodeTriggerIcon";
import { triggerTypes } from "../lib/utils";

export function DebugNodeInfo({ id, data }: Pick<FlowNode, "id" | "data">) {
  if (!WF_DEBUG_INFO) {
    return null;
  }
  return (
    <div className="flex flex-col absolute top-0 bottom-0 my-auto right-0 translate-x-[calc(100%+20px)]">
      <div
        className={`h-fit bg-black text-pink-500 font-mono text-[10px] px-1 py-1`}
      >
        {id}
      </div>
      <details className="bg-black text-pink-500 font-mono text-[10px] px-1 py-1">
        <summary>data=</summary>
        <pre className="text-xs leading-none text-gray-500">
          {JSON.stringify(data, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function IconUrlProvider(data: FlowNode["data"]) {
  const { componentType, type } = data || {};
  if (type === "alert" || type === "workflow" || type === "trigger" || !type)
    return "/keep.png";
  if (type === "incident" || type === "workflow" || type === "trigger" || !type)
    return "/keep.png";
  return `/icons/${type
    ?.replace("step-", "")
    ?.replace("action-", "")
    ?.replace("__end", "")
    ?.replace("condition-", "")}-icon.png`;
}

function WorkflowNode({ id, data }: FlowNode) {
  const {
    selectedNode,
    setSelectedNode,
    setEditorOpen,
    synced,
    validationErrors,
  } = useWorkflowStore();
  const type = data?.type
    ?.replace("step-", "")
    ?.replace("action-", "")
    ?.replace("condition-", "")
    ?.replace("__end", "")
    ?.replace("trigger_", "");

  const isEmptyNode = !!data?.type?.includes("empty");
  const specialNodeCheck = ["start", "end"].includes(type);
  const errorMessage =
    validationErrors?.[data?.name] || validationErrors?.[data?.id];
  const isError = !!errorMessage;
  const isTrigger = triggerTypes.includes(type);

  function handleNodeClick(e: React.MouseEvent<HTMLDivElement>) {
    e.stopPropagation();
    if (!synced) {
      toast(
        "Please save the previous step or wait while properties sync with the workflow."
      );
      return;
    }
    if (data?.notClickable) {
      return;
    }
    if (specialNodeCheck || id?.includes("end")) {
      return;
    }
    setEditorOpen(true);
    setSelectedNode(id);
  }

  if (
    data.id === "trigger_start" ||
    data.id === "trigger_end" ||
    data.id === "end"
  ) {
    return (
      <div
        className={clsx(
          "w-full h-full flex items-center justify-center",
          data.id === "end" && "opacity-0"
        )}
      >
        <DebugNodeInfo id={id} data={data} />
        <div
          className={clsx(
            "bg-gray-50 border border-gray-500 px-3 py-1 relative capitalize text-center flex items-center justify-center gap-1",
            data.id === "trigger_start" ? "rounded-full" : "rounded-md"
          )}
        >
          {data.name}
          {isError && (
            <Tooltip
              content={errorMessage}
              className="text-center max-w-48 text-sm"
            >
              <ExclamationCircleIcon className="size-5 text-red-500" />
            </Tooltip>
          )}
        </div>
        {data.id !== "trigger_start" && (
          <Handle type="target" position={Position.Top} className="w-32" />
        )}
        {data.id !== "end" && (
          <Handle type="source" position={Position.Bottom} className="w-32" />
        )}
      </div>
    );
  }

  return (
    <>
      {!specialNodeCheck && (
        <div
          className={clsx(
            "flex shadow-md border-2 w-full h-full cursor-pointer transition-colors",
            id === selectedNode
              ? "border-orange-500 bg-orange-50"
              : "border-stone-400 bg-white",
            id !== selectedNode && "hover:bg-gray-50",
            id !== selectedNode && isError && "border-red-500",
            isTrigger ? "rounded-full" : "rounded-md"
          )}
          onClick={handleNodeClick}
          style={{
            opacity: data.isLayouted ? 1 : 0,
            borderStyle: isEmptyNode ? "dashed" : "",
          }}
        >
          <DebugNodeInfo id={id} data={data} />
          {isEmptyNode && (
            <div className="p-2 flex-1 flex flex-col items-center justify-center">
              <GoPlus className="w-8 h-8 text-gray-600 font-bold p-0" />
              {selectedNode === id && (
                <div className="text-gray-600 font-bold text-center">
                  Go to Toolbox
                </div>
              )}
            </div>
          )}
          {!isEmptyNode && (
            <div className="container px-4 py-2 flex-1 flex flex-row items-center justify-between gap-2 flex-wrap">
              {/* FIX: not updating when the trigger is changed */}
              {data.componentType === "trigger" ? (
                <NodeTriggerIcon
                  key={data?.properties?.source}
                  nodeData={data}
                />
              ) : (
                <DynamicImageProviderIcon
                  src={IconUrlProvider(data) || "/keep.png"}
                  alt={data?.type}
                  className="object-cover w-8 h-8 rounded-full bg-gray-100"
                  width={32}
                  height={32}
                />
              )}
              <div className="flex-1 flex-col gap-2 flex-wrap truncate">
                <div className="text-lg font-bold truncate flex items-center gap-1">
                  {data?.name}
                  {isError && (
                    <Tooltip
                      content={errorMessage}
                      className="text-center max-w-48 text-sm"
                    >
                      <ExclamationCircleIcon className="size-5 text-red-500" />
                    </Tooltip>
                  )}
                </div>
                <div className="text-gray-500 truncate">{type}</div>
              </div>
              <div>
                <NodeMenu data={data} id={id} />
              </div>
            </div>
          )}

          <Handle type="target" position={Position.Top} className="w-32" />
          <Handle type="source" position={Position.Bottom} className="w-32" />
        </div>
      )}

      {specialNodeCheck && (
        <div
          style={{
            opacity: data.isLayouted ? 1 : 0,
          }}
          onClick={(e) => {
            e.stopPropagation();
            if (!synced) {
              toast(
                "Please save the previous step or wait while properties sync with the workflow."
              );
              return;
            }
            if (specialNodeCheck || id?.includes("end")) {
              setEditorOpen(true);
              return;
            }
            setSelectedNode(id);
          }}
        >
          <div className={`flex flex-col items-center justify-center`}>
            {type === "start" && (
              <MdNotStarted className="size-20 bg-orange-500 text-white rounded-full font-bold mb-2" />
            )}
            {type === "end" && (
              <GoSquareFill className="size-20 bg-orange-500 text-white rounded-full font-bold mb-2" />
            )}
            {["threshold", "assert", "foreach"].includes(type) && (
              <div
                className={`border-2 ${
                  id === selectedNode ? "border-orange-500" : "border-stone-400"
                }`}
              >
                {id.includes("end") ? (
                  <PiSquareLogoFill className="size-20 rounded bg-white-400 p-2" />
                ) : (
                  <Image
                    src={IconUrlProvider(data) || "/keep.png"}
                    alt={data?.type}
                    className="object-contain size-20 rounded bg-white-400 p-2"
                    width={32}
                    height={32}
                  />
                )}
              </div>
            )}
            {"start" === type && (
              <Handle
                type="source"
                position={Position.Bottom}
                className="w-32"
              />
            )}

            {"end" === type && (
              <Handle type="target" position={Position.Top} className="w-32" />
            )}
          </div>
        </div>
      )}
    </>
  );
}

export default memo(WorkflowNode);
