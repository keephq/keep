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
import {
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/20/solid";
import { Tooltip } from "@/shared/ui/Tooltip";
import { NodeTriggerIcon } from "@/entities/workflows/ui/NodeTriggerIcon";
import { normalizeStepType, triggerTypes } from "../lib/utils";
import { getTriggerDescriptionFromStep } from "@/entities/workflows/lib/getTriggerDescription";
import { ValidationError } from "@/entities/workflows/lib/validation";
import { useConfig } from "@/utils/hooks/useConfig";

export function DebugNodeInfo({ id, data }: Pick<FlowNode, "id" | "data">) {
  const { data: config } = useConfig();
  if (!config?.KEEP_WORKFLOW_DEBUG) {
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
  const { type } = data || {};
  if (type === "alert" || type === "workflow" || type === "trigger" || !type)
    return "/keep.png";
  if (type === "incident" || type === "workflow" || type === "trigger" || !type)
    return "/keep.png";
  return `/icons/${normalizeStepType(type)}-icon.png`;
}

function ErrorIcon({ error }: { error: ValidationError | null }) {
  if (!error) {
    return null;
  }
  const errorMessage = error?.[0];
  const severity = error?.[1];
  switch (severity) {
    case "error": {
      return (
        <Tooltip
          content={errorMessage}
          className="text-center max-w-48 text-sm"
        >
          <ExclamationCircleIcon className="size-5 text-red-500" />
        </Tooltip>
      );
    }
    case "warning": {
      return (
        <Tooltip
          content={errorMessage}
          className="text-center max-w-48 text-sm"
        >
          <ExclamationTriangleIcon className="size-5 text-yellow-500" />
        </Tooltip>
      );
    }
    default: {
      return null;
    }
  }
}

function WorkflowNode({ id, data }: FlowNode) {
  const {
    selectedNode,
    setSelectedNode,
    isEditorSyncedWithNodes: synced,
    validationErrors,
  } = useWorkflowStore();
  const type = normalizeStepType(data?.type ?? "");

  const isEmptyNode = !!data?.type?.includes("empty");
  const specialNodeCheck = ["start", "end"].includes(type);
  const error = validationErrors?.[data?.name] || validationErrors?.[data?.id];
  const isError = error?.[1] === "error";
  const isWarning = error?.[1] === "warning";
  const isTrigger =
    data?.componentType === "trigger" && triggerTypes.includes(type);

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

  let displayName = data?.name;
  let subtitle = isTrigger ? getTriggerDescriptionFromStep(data) : data?.type;

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
            id !== selectedNode && isError && "!border-red-500",
            id !== selectedNode && isWarning && "!border-yellow-500",
            isTrigger ? "rounded-full" : "rounded-md"
          )}
          onClick={handleNodeClick}
          style={{
            opacity: data.isLayouted ? 1 : 0,
            borderStyle: isEmptyNode ? "dashed" : "",
          }}
          data-testid="workflow-node"
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
              {data.componentType === "trigger" ? (
                <NodeTriggerIcon
                  key={
                    data?.type === "alert"
                      ? data?.properties?.filters?.source
                      : data?.id
                  }
                  nodeData={data}
                />
              ) : (
                <DynamicImageProviderIcon
                  src={IconUrlProvider(data) || "/keep.png"}
                  alt={data?.type}
                  className="object-cover w-8 h-8"
                  width={32}
                  height={32}
                />
              )}
              <div className="flex-1 flex-col flex-wrap min-w-0">
                <div className="text-lg font-bold flex items-center gap-1 leading-tight">
                  <span className="truncate" title={displayName}>
                    {displayName}
                  </span>
                  <ErrorIcon error={error} />
                </div>
                <div className="text-gray-500 truncate">{subtitle}</div>
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
