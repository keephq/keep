import React, { useState, useEffect, useMemo } from "react";
import { Disclosure } from "@headlessui/react";
import { Subtitle } from "@tremor/react";
import { IoChevronUp } from "react-icons/io5";
import { useWorkflowStore } from "@/entities/workflows";
import clsx from "clsx";
import { V2Step, V2StepTrigger } from "@/entities/workflows/model/types";
import { DynamicImageProviderIcon, TextInput } from "@/components/ui";
import { NodeTriggerIcon } from "@/entities/workflows/ui/NodeTriggerIcon";
import { triggerTypes } from "../lib/utils";

type GroupedMenuBaseProps = {
  searchTerm: string;
  resetSearchTerm: () => void;
  isDraggable?: boolean;
};

type GroupedMenuProps = GroupedMenuBaseProps &
  (
    | {
        name: "Triggers";
        steps: V2StepTrigger[];
      }
    | {
        name: string;
        steps: Omit<V2Step, "id">[];
      }
  );

const GroupedMenu = ({
  name,
  steps,
  searchTerm,
  resetSearchTerm,
  isDraggable = true,
}: GroupedMenuProps) => {
  const [isOpen, setIsOpen] = useState(!!searchTerm || isDraggable);
  const { selectedNode, selectedEdge, addNodeBetweenSafe } = useWorkflowStore();

  useEffect(() => {
    setIsOpen(!!searchTerm || !isDraggable);
  }, [searchTerm, isDraggable]);

  const handleAddNode = (
    e: React.MouseEvent<HTMLLIElement>,
    step: V2StepTrigger | Omit<V2Step, "id">
  ) => {
    e.stopPropagation();
    e.preventDefault();
    if (isDraggable) {
      return;
    }
    const nodeOrEdgeId = selectedNode || selectedEdge;
    const type = selectedNode ? "node" : "edge";
    if (!nodeOrEdgeId) {
      return;
    }
    const newNodeId = addNodeBetweenSafe(nodeOrEdgeId, step, type);
    if (newNodeId) {
      resetSearchTerm();
    }
  };

  function IconUrlProvider(data: any) {
    const { type } = data || {};
    if (type === "alert" || type === "workflow") return "/keep.png";
    if (type === "incident" || type === "workflow") return "/keep.png";
    return `/icons/${type
      ?.replace("step-", "")
      ?.replace("action-", "")
      ?.replace("condition-", "")}-icon.png`;
  }

  const handleDragStart = (
    event: React.DragEvent<HTMLLIElement>,
    step: any
  ) => {
    if (!isDraggable) {
      event.stopPropagation();
      event.preventDefault();
    }
    event.dataTransfer.setData("application/reactflow", JSON.stringify(step));
    event.dataTransfer.effectAllowed = "move";
  };

  return (
    <Disclosure
      as="div"
      className="space-y-1"
      defaultOpen={isOpen}
      key={isOpen ? "open" : "closed" + name}
    >
      {({ open }) => {
        return (
          <>
            <Disclosure.Button className="w-full flex justify-between items-center p-2">
              <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
                {name}
              </Subtitle>
              <IoChevronUp
                className={clsx({ "rotate-180": open }, "mr-2 text-slate-400")}
              />
            </Disclosure.Button>
            {(open || !isDraggable) && (
              <Disclosure.Panel
                as="ul"
                className="space-y-2 overflow-auto min-w-[max-content] p-2 pr-4"
              >
                {steps.length > 0 &&
                  steps.map((step) => (
                    <li
                      key={step.type}
                      className={clsx(
                        "dndnode p-2 my-1 border border-gray-300 rounded cursor-pointer truncate flex justify-start gap-2 items-center hover:bg-gray-50 transition-colors",
                        triggerTypes.includes(step.type) && "rounded-full"
                      )}
                      onDragStart={(event) =>
                        handleDragStart(event, { ...step })
                      }
                      draggable={isDraggable}
                      title={step.name}
                      onClick={(e) => handleAddNode(e, step)}
                    >
                      {step.componentType === "trigger" ? (
                        <NodeTriggerIcon nodeData={step} />
                      ) : (
                        <DynamicImageProviderIcon
                          src={IconUrlProvider(step) || "/keep.png"}
                          alt={step?.type}
                          className="object-contain aspect-auto"
                          width={32}
                          height={32}
                        />
                      )}
                      <Subtitle className="truncate">{step.name}</Subtitle>
                    </li>
                  ))}
              </Disclosure.Panel>
            )}
          </>
        );
      }}
    </Disclosure>
  );
};

export const WorkflowToolbox = ({ isDraggable }: { isDraggable?: boolean }) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [isVisible, setIsVisible] = useState(true);
  const [open, setOpen] = useState(true);
  const { toolboxConfiguration, selectedNode, selectedEdge, nodes } =
    useWorkflowStore();

  const showOnlyTriggers = selectedEdge?.startsWith("etrigger_start");
  // User cannot add conditions inside a condition
  const showConditions =
    !selectedEdge?.endsWith("empty_true") &&
    !selectedEdge?.endsWith("empty_false") &&
    !selectedNode?.endsWith("empty_true") &&
    !selectedNode?.endsWith("empty_false");
  // User cannot add foreach inside a foreach
  const showForeach =
    !selectedEdge?.endsWith("foreach") &&
    !selectedNode?.endsWith("empty_foreach");

  useEffect(() => {
    const isOpen =
      (!!selectedNode && selectedNode.includes("empty")) || !!selectedEdge;
    setOpen(isOpen);
    setIsVisible(isDraggable || isOpen);
  }, [selectedNode, selectedEdge, isDraggable]);

  const triggerNodeMap = nodes
    .filter((node) =>
      ["interval", "manual", "alert", "incident"].includes(node?.id)
    )
    .reduce(
      (obj: any, node) => {
        obj[node.id] = true;
        return obj;
      },
      {} as Record<string, boolean>
    );

  const filteredGroups = useMemo(() => {
    if (!toolboxConfiguration) {
      return [];
    }
    return (
      toolboxConfiguration.groups
        .filter((group) => {
          if (showOnlyTriggers) {
            return group?.name === "Triggers";
          }
          if (!showConditions) {
            return group?.name !== "Conditions" && group?.name !== "Triggers";
          }
          if (!showForeach) {
            return group?.name !== "Misc" && group?.name !== "Triggers";
          }
          return group?.name !== "Triggers";
        })
        .map((group) => ({
          ...group,
          steps: group?.steps?.filter(
            (step) =>
              step?.name?.toLowerCase().includes(searchTerm?.toLowerCase()) &&
              (!("id" in step) || !triggerNodeMap[step?.id])
          ),
        })) || []
    );
  }, [toolboxConfiguration, showOnlyTriggers, searchTerm, triggerNodeMap]);

  const checkForSearchResults =
    searchTerm && !!filteredGroups?.find((group) => group?.steps?.length > 0);

  if (!open) {
    return null;
  }

  return (
    <div
      className={clsx(
        "bg-white transition-transform z-40 shrink-0",
        isVisible ? "h-full" : "shadow-lg"
      )}
    >
      <div className="relative h-full flex flex-col px-2">
        {/* Sticky header */}
        <div className="sticky top-0 left-0 z-10 bg-white">
          <Subtitle className="font-medium p-2">
            Add {showOnlyTriggers ? "trigger" : "step"}
          </Subtitle>
          <div className="flex items-center justify-between p-2 pt-0 bg-white">
            <TextInput
              type="text"
              placeholder="Search..."
              className="w-full"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        {/* Scrollable list */}
        {(isVisible || checkForSearchResults) && (
          <div className="flex-1 overflow-y-auto pt-2 space-y-4 overflow-hidden">
            {filteredGroups.length > 0 &&
              filteredGroups.map((group) => (
                <GroupedMenu
                  key={group.name}
                  name={group.name}
                  // TODO: fix type
                  steps={group.steps as any}
                  searchTerm={searchTerm}
                  resetSearchTerm={() => setSearchTerm("")}
                  isDraggable={isDraggable}
                />
              ))}
          </div>
        )}
      </div>
    </div>
  );
};
