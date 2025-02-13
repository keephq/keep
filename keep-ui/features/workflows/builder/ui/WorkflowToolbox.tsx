import React, { useState, useEffect, useMemo } from "react";
import { Disclosure } from "@headlessui/react";
import { Subtitle, Title } from "@tremor/react";
import { IoChevronUp } from "react-icons/io5";
import { useWorkflowStore } from "@/entities/workflows";
import { PiDiamondsFourFill } from "react-icons/pi";
import clsx from "clsx";
import { V2Step } from "@/entities/workflows/model/types";
import { CursorArrowRaysIcon } from "@heroicons/react/24/outline";
import { DynamicImageProviderIcon } from "@/components/ui";

const GroupedMenu = ({
  name,
  steps,
  searchTerm,
  isDraggable = true,
}: {
  name: string;
  steps: any[];
  searchTerm: string;
  isDraggable?: boolean;
}) => {
  const [isOpen, setIsOpen] = useState(!!searchTerm || isDraggable);
  const { selectedNode, selectedEdge, addNodeBetween } = useWorkflowStore();

  useEffect(() => {
    setIsOpen(!!searchTerm || !isDraggable);
  }, [searchTerm, isDraggable]);

  const handleAddNode = (e: React.MouseEvent<HTMLLIElement>, step: V2Step) => {
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
    addNodeBetween(nodeOrEdgeId, step, type);
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

  function getTriggerIcon(step: any) {
    const { type } = step;
    switch (type) {
      case "manual":
        return <CursorArrowRaysIcon className="size-8" />;
      case "interval":
        return <PiDiamondsFourFill size={32} />;
    }
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
                  steps.map((step: any) => (
                    <li
                      key={step.type}
                      className="dndnode p-2 my-1 border border-gray-300 rounded cursor-pointer truncate flex justify-start gap-2 items-center hover:bg-gray-50 transition-colors"
                      onDragStart={(event) =>
                        handleDragStart(event, { ...step })
                      }
                      draggable={isDraggable}
                      title={step.name}
                      onClick={(e) => handleAddNode(e, step)}
                    >
                      {getTriggerIcon(step)}
                      {!!step &&
                        !["interval", "manual"].includes(step.type) && (
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

  const showTriggers = selectedEdge?.startsWith("etrigger_start");

  useEffect(() => {
    const isOpen =
      (!!selectedNode && selectedNode.includes("empty")) || !!selectedEdge;
    setOpen(isOpen);
    setIsVisible(isDraggable || isOpen);
  }, [selectedNode, selectedEdge, isDraggable]);

  const triggerNodeMap = nodes
    .filter((node: any) =>
      ["interval", "manual", "alert", "incident"].includes(node?.id)
    )
    .reduce(
      (obj: any, node: any) => {
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
        .filter((group: any) =>
          showTriggers ? group?.name === "Triggers" : group?.name !== "Triggers"
        )
        .map((group: any) => ({
          ...group,
          steps: group?.steps?.filter(
            (step: any) =>
              step?.name?.toLowerCase().includes(searchTerm?.toLowerCase()) &&
              !triggerNodeMap[step?.id]
          ),
        })) || []
    );
  }, [toolboxConfiguration, showTriggers, searchTerm, triggerNodeMap]);

  const checkForSearchResults =
    searchTerm &&
    !!filteredGroups?.find((group: any) => group?.steps?.length > 0);

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
      <div className="relative h-full flex flex-col">
        {/* Sticky header */}
        <div className="sticky top-0 left-0 z-10 bg-white">
          <Title className="p-2">Add {showTriggers ? "trigger" : "step"}</Title>
          <div className="flex items-center justify-between p-2 pt-0 bg-white">
            <input
              type="text"
              placeholder="Search..."
              className="p-2 border border-gray-300 rounded w-full"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        {/* Scrollable list */}
        {(isVisible || checkForSearchResults) && (
          <div className="flex-1 overflow-y-auto pt-2 space-y-4 overflow-hidden">
            {filteredGroups.length > 0 &&
              filteredGroups.map((group: Record<string, any>) => (
                <GroupedMenu
                  key={group.name}
                  name={group.name}
                  steps={group.steps}
                  searchTerm={searchTerm}
                  isDraggable={isDraggable}
                />
              ))}
          </div>
        )}
      </div>
    </div>
  );
};
