import React, { useState, useEffect, useMemo } from "react";
import { Disclosure } from "@headlessui/react";
import { Subtitle, Switch } from "@tremor/react";
import { IoChevronUp, IoClose } from "react-icons/io5";
import Image from "next/image";
import { IoIosArrowDown } from "react-icons/io";
import useStore from "./builder-store";
import { PiDiamondsFourFill } from "react-icons/pi";
import clsx from "clsx";
import { V2Step } from "@/app/(keep)/workflows/builder/types";
import { CursorArrowRaysIcon } from "@heroicons/react/24/outline";

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
  const { selectedNode, selectedEdge, addNodeBetween } = useStore();

  useEffect(() => {
    setIsOpen(!!searchTerm || !isDraggable);
  }, [searchTerm, isDraggable]);

  const handleAddNode = (e: React.MouseEvent<HTMLLIElement>, step: V2Step) => {
    e.stopPropagation();
    e.preventDefault();
    if (isDraggable) {
      return;
    }
    addNodeBetween(
      selectedNode || selectedEdge,
      step,
      selectedNode ? "node" : "edge"
    );
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
    <Disclosure as="div" className="space-y-1">
      {({ open }) => (
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
                    key={`${step.type}__${step.id || step.name}`}
                    className="dndnode p-2 my-1 border border-gray-300 rounded cursor-pointer truncate flex justify-start gap-2 items-center"
                    onDragStart={(event) => handleDragStart(event, { ...step })}
                    draggable={isDraggable}
                    title={step.name}
                    onClick={(e) => handleAddNode(e, step)}
                  >
                    {getTriggerIcon(step)}
                    {!!step && !["interval", "manual"].includes(step.type) && (
                      <Image
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
      )}
    </Disclosure>
  );
};

const DragAndDropSidebar = ({ isDraggable }: { isDraggable?: boolean }) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [isVisible, setIsVisible] = useState(false);
  const [open, setOpen] = useState(false);
  const [showinstalled, setShowInstalled] = useState(true);
  const { toolboxConfiguration, selectedNode, selectedEdge, nodes, edges } =
    useStore();

  useEffect(() => {
    setOpen(
      (!!selectedNode && selectedNode.includes("empty")) || !!selectedEdge
    );
    setIsVisible(!isDraggable);
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
    const checkInstalled = (step: V2Step, groupName: string) => {
      if (!showinstalled) {
        return true;
      }

      if (["Conditions", "Misc", "Triggers"].includes(groupName)) {
        return true;
      }

      return step?.installed;
    };
    let finalGroups =
      toolboxConfiguration?.groups?.map((group: any) => ({
        ...group,
        steps: group?.steps?.filter(
          (step: any) =>
            checkInstalled(step, group.name) &&
            step?.name?.toLowerCase().includes(searchTerm?.toLowerCase()) &&
            !triggerNodeMap[step?.id]
        ),
      })) || [];
    const selectedAddEdge = edges.find((edge) => edge.id === selectedEdge);
    if (selectedEdge && selectedAddEdge) {
      finalGroups = finalGroups.filter(
        (group: { name: string }) =>
          (group?.name == "Triggers" &&
            selectedAddEdge.source === "trigger_start") ||
          (selectedAddEdge.source !== "trigger_start" &&
            group?.name !== "Triggers")
      );
    }
    return finalGroups;
  }, [
    toolboxConfiguration?.groups,
    edges,
    selectedEdge,
    showinstalled,
    searchTerm,
    triggerNodeMap,
  ]);

  const checkForSearchResults =
    searchTerm &&
    !!filteredGroups?.find((group: any) => group?.steps?.length > 0);

  if (!open) {
    return null;
  }

  return (
    <div
      className={`absolute top-50 left-2 rounded border-2 broder-gray-300 bg-white transition-transform duration-300 z-50 ${
        isVisible ? "h-[88%] border-b-0" : "shadow-lg"
      }`}
      style={{ width: "280px" }} // Set a fixed width
    >
      <div className="relative h-full flex flex-col">
        {/* Sticky header */}
        <div className="sticky top-0 left-0 z-10">
          <div className="flex justify-between">
            <h1 className="p-3 font-bold">Toolbox</h1>
          </div>
          <div className="flex items-center justify-between p-2 pt-0 border-b-2 bg-white">
            <input
              type="text"
              placeholder="Search..."
              className="p-2 border border-gray-300 rounded w-full"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
            <button
              className="p-2 text-gray-500"
              onClick={() => {
                setIsVisible(!isVisible);
                setSearchTerm("");
              }}
            >
              {isVisible || checkForSearchResults ? (
                <IoClose size={20} />
              ) : (
                <IoIosArrowDown size={20} />
              )}
            </button>
          </div>
        </div>

        {/* Scrollable list */}
        {(isVisible || checkForSearchResults) && (
          <div className="flex-1 overflow-y-auto overflow-hidden">
            <div className="flex flex-col items-end mr-4">
              <div>Installed</div>
              <Switch
                id="installed"
                name="Installed"
                checked={showinstalled}
                onChange={setShowInstalled}
              />
            </div>
            <div className="space-y-4 pt-4">
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
          </div>
        )}
      </div>
    </div>
  );
};

export default DragAndDropSidebar;
