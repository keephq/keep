import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import NodeMenu from "./NodeMenu";
import { useWorkflowStore } from "@/entities/workflows";
import Image from "next/image";
import { GoPlus } from "react-icons/go";
import { MdNotStarted } from "react-icons/md";
import { GoSquareFill } from "react-icons/go";
import { PiDiamondsFourFill, PiSquareLogoFill } from "react-icons/pi";
import { BiSolidError } from "react-icons/bi";
import { toast } from "react-toastify";
import { FlowNode } from "@/entities/workflows/model/types";
import { CursorArrowRaysIcon } from "@heroicons/react/24/outline";
import { DynamicImageProviderIcon } from "@/components/ui";
import clsx from "clsx";

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
    setGlobalEditorOpen,
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
  const isError =
    !!validationErrors?.[data?.name] || !!validationErrors?.[data?.id];

  function getTriggerIcon(step: any) {
    const { type } = step;
    switch (type) {
      case "manual":
        return <CursorArrowRaysIcon className="size-8" />;
      case "interval":
        return <PiDiamondsFourFill size={32} />;
    }
  }

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
    if (specialNodeCheck || id?.includes("end") || id?.includes("empty")) {
      if (id?.includes("empty")) {
        setSelectedNode(id);
      }
      setGlobalEditorOpen(true);
      return;
    }
    setSelectedNode(id);
  }

  if (data.id === "trigger_start" || data.id === "trigger_end") {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <span className="rounded-full bg-gray-50 border border-gray-500 px-4 py-2 flex items-center justify-center relative">
          {data.name}
          {isError && (
            <BiSolidError className="size-10  text-red-500 absolute right-[-20px] top-[-20px]" />
          )}
        </span>
        <Handle type="target" position={Position.Top} className="w-32" />
        <Handle type="source" position={Position.Bottom} className="w-32" />
      </div>
    );
  }

  return (
    <>
      {!specialNodeCheck && (
        <div
          className={clsx(
            "flex shadow-md rounded-md border-2 w-full h-full cursor-pointer transition-colors",
            id === selectedNode
              ? "border-orange-500 bg-orange-50"
              : "border-stone-400 bg-white",
            id !== selectedNode && "hover:bg-gray-50",
            id !== selectedNode && isError && "border-red-500"
          )}
          onClick={handleNodeClick}
          style={{
            opacity: data.isLayouted ? 1 : 0,
            borderStyle: isEmptyNode ? "dashed" : "",
          }}
        >
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
          {isError && (
            <BiSolidError className="size-16  text-red-500 absolute right-[-40px] top-[-40px]" />
          )}
          {!isEmptyNode && (
            <div className="container p-2 flex-1 flex flex-row items-center justify-between gap-2 flex-wrap">
              {getTriggerIcon(data)}
              {!!data && !["interval", "manual"].includes(data.type) && (
                <DynamicImageProviderIcon
                  src={IconUrlProvider(data) || "/keep.png"}
                  alt={data?.type}
                  className="object-cover w-8 h-8 rounded-full bg-gray-100"
                  width={32}
                  height={32}
                />
              )}
              <div className="flex-1 flex-col gap-2 flex-wrap truncate">
                <div className="text-lg font-bold truncate">{data?.name}</div>
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
              setGlobalEditorOpen(true);
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
