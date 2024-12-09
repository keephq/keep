import React, { Fragment } from "react";
import { Menu, Transition } from "@headlessui/react";
import { Icon } from "@tremor/react";
import { PencilIcon, TrashIcon } from "@heroicons/react/24/outline";
import { Bars3Icon } from "@heroicons/react/20/solid";
import { FiSave } from "react-icons/fi";

interface MenuButtonProps {
  onEdit: () => void;
  onDelete: () => void;
  onSave?: () => void;
}

const MenuButton: React.FC<MenuButtonProps> = ({
  onEdit,
  onDelete,
  onSave,
}) => {
  const stopPropagation = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
  };

  return (
    <div className="w-44 text-right">
      <Menu as="div" className="relative inline-block text-left z-10">
        <div>
          <Menu.Button
            className="inline-flex w-full justify-center rounded-md text-sm mt-2"
            onClick={stopPropagation}
          >
            <Icon
              size="sm"
              icon={Bars3Icon}
              className="hover:bg-gray-100 w-8 h-8"
              color="gray"
            />
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
          <Menu.Items className="absolute right-0 mt-2 w-36 origin-top-right divide-y divide-gray-100 rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
            <div className="px-1 py-1">
              <Menu.Item>
                {({ active }) => (
                  <button
                    onClick={(e) => {
                      stopPropagation(e);
                      onEdit();
                    }}
                    className={`${
                      active ? "bg-slate-200" : "text-gray-900"
                    } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                  >
                    <PencilIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                    Edit
                  </button>
                )}
              </Menu.Item>
              <Menu.Item>
                {({ active }) => (
                  <button
                    onClick={(e) => {
                      stopPropagation(e);
                      onDelete();
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
              {onSave && (
                <Menu.Item>
                  {({ active }) => (
                    <button
                      onClick={(e) => {
                        stopPropagation(e);
                        onSave();
                      }}
                      className={`${
                        active ? "bg-slate-200" : "text-gray-900"
                      } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                    >
                      <FiSave className="mr-2 h-4 w-4" aria-hidden="true" />
                      Save
                    </button>
                  )}
                </Menu.Item>
              )}
            </div>
          </Menu.Items>
        </Transition>
      </Menu>
    </div>
  );
};

export default MenuButton;
