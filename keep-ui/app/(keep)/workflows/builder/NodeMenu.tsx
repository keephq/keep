import { Menu, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { CiSquareChevDown } from "react-icons/ci";
import { TrashIcon } from "@heroicons/react/24/outline";
import useStore from "./builder-store";
import { IoMdSettings } from "react-icons/io";
import { FlowNode } from "@/app/(keep)/workflows/builder/types";

export default function NodeMenu({
  data,
  id,
}: {
  data: FlowNode["data"];
  id: string;
}) {
  const stopPropagation = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
  };
  const hideMenu =
    data?.type?.includes("empty") ||
    id?.includes("end") ||
    id?.includes("start");
  const { deleteNodes, setSelectedNode, setStepEditorOpenForNode } = useStore();

  return (
    <>
      {data && !hideMenu && (
        <Menu as="div" className="relative inline-block text-left">
          <div>
            <Menu.Button
              className="inline-flex w-full justify-center rounded-md text-sm"
              onClick={stopPropagation}
            >
              <CiSquareChevDown className="size-6 text-gray-500 hover:text-gray-700" />
            </Menu.Button>
          </div>
          <Transition
            as={Fragment}
            enter="transition ease-out duration-100"
            enterFrom="transform opacity-0 scale-95"
            enterTo="transform opacity-100 scale-100"
            leave="transition ease-in duration-75"
            leaveFrom="transform opacity-100 scale-100"
            leaveTo="transform opacity-0 scale-95"
          >
            <Menu.Items className="absolute right-0 w-36 origin-top-right divide-y divide-gray-100 rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
              <div className="px-1 py-1">
                <Menu.Item>
                  {({ active }) => (
                    <button
                      onClick={(e) => {
                        stopPropagation(e);
                        deleteNodes(id);
                      }}
                      className={`${
                        active ? "bg-slate-200" : "text-gray-900"
                      } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                    >
                      <TrashIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                      Delete
                    </button>
                  )}
                </Menu.Item>
                <Menu.Item>
                  {({ active }) => (
                    <button
                      onClick={(e) => {
                        stopPropagation(e);
                        setSelectedNode(id);
                        setStepEditorOpenForNode(id);
                      }}
                      className={`${
                        active ? "bg-slate-200" : "text-gray-900"
                      } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                    >
                      <IoMdSettings
                        className="mr-2 h-4 w-4"
                        aria-hidden="true"
                      />
                      Properties
                    </button>
                  )}
                </Menu.Item>
              </div>
            </Menu.Items>
          </Transition>
        </Menu>
      )}
    </>
  );
}
