import React, { useState, useEffect } from "react";
import classNames from "classnames";
import { Disclosure } from "@headlessui/react";
import { Subtitle } from "@tremor/react";
import { IoChevronUp, IoClose } from "react-icons/io5";
import Image from "next/image";
import { IoIosArrowDown } from "react-icons/io";

const GroupedMenu = ({ name, steps, searchTerm }:{name:string, steps:any[], searchTerm:string}) => {
  const [isOpen, setIsOpen] = useState(!!searchTerm);

  useEffect(() => {
    setIsOpen(!!searchTerm);
  }, [searchTerm]);

  function IconUrlProvider(data:any) {
    const { type } = data || {};
    if (type === "alert" || type === "workflow") return "/keep.png";
    return `/icons/${type
      ?.replace("step-", "")
      ?.replace("action-", "")
      ?.replace("condition-", "")}-icon.png`;
  }

  const handleDragStart = (event:React.DragEvent<HTMLLIElement>, step:any) => {
    event.dataTransfer.setData("application/reactflow", JSON.stringify(step));
    event.dataTransfer.effectAllowed = "move";
  };

  return (
    <Disclosure as="div" className="space-y-1" defaultOpen={isOpen}>
      {({ open }) => (
        <>
          <Disclosure.Button className="w-full flex justify-between items-center p-2">
            <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
              {name}
            </Subtitle>
            <IoChevronUp
              className={classNames(
                { "rotate-180": open },
                "mr-2 text-slate-400"
              )}
            />
          </Disclosure.Button>
          {open && (
            <Disclosure.Panel
              as="ul"
              className="space-y-2 overflow-auto min-w-[max-content] p-2 pr-4"
            >
              {steps.length > 0 &&
                steps.map((step:any) => (
                  <li
                    key={step.type}
                    className="dndnode p-2 my-1 border border-gray-300 rounded cursor-pointer truncate flex justify-start gap-2 items-center"
                    onDragStart={(event) => handleDragStart(event, { ...step })}
                    draggable
                    title={step.name}
                  >
                    <Image
                      src={IconUrlProvider(step) || "/keep.png"}
                      alt={step?.type}
                      className="object-contain aspect-auto"
                      width={32}
                      height={32}
                    />
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

const DragAndDropSidebar = ({ toolboxConfiguration }: { toolboxConfiguration?: Record<string, any> }) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [isVisible, setIsVisible] = useState(false);

  const filteredGroups =
    toolboxConfiguration?.groups?.map((group: any) => ({
      ...group,
      steps: group?.steps?.filter((step: any) =>
        step?.name?.toLowerCase().includes(searchTerm?.toLowerCase())
      ),
    })) || [];

  const checkForSearchResults =  searchTerm && !!filteredGroups?.find((group:any) => group?.steps?.length>0);


  return (
    <div
      className={`absolute top-0 left-0 rounded border-2 border-gray-200 bg-white transition-transform duration-300 z-50 overflow-y-auto ${isVisible ? ' h-full' : 'shadow-lg'}`}
  
      style={{ width: '280px' }} // Set a fixed width
    >
            <div className="flex items-center justify-between p-2 border-b border-gray-200">

      
        <input
          type="text"
          placeholder="Search..."
          className="p-2 border border-gray-300 rounded w-full"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
         <button
          className="p-2 text-gray-500"
          onClick={() => {setIsVisible(!isVisible); setSearchTerm('');}}
        >
          {(isVisible || checkForSearchResults) ? <IoClose size={20} /> : <IoIosArrowDown size={20} />}
        </button>
      </div>
      {(isVisible || checkForSearchResults) &&<div className="pt-6 space-y-4">
        {filteredGroups.length > 0 &&
          filteredGroups.map((group:Record<string,any>) => (
            <GroupedMenu
              key={group.name}
              name={group.name}
              steps={group.steps}
              searchTerm={searchTerm}
            />
          ))}
      </div>}
    </div>
  );
};

export default DragAndDropSidebar;
