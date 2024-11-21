import React, { Fragment } from "react";
import { Menu, Transition } from "@headlessui/react";
import { Icon, Subtitle } from "@tremor/react";
import { EllipsisHorizontalIcon } from "@heroicons/react/24/outline";

interface TitleProps {
  title: string;
  onEdit: () => void;
}

const Title: React.FC<TitleProps> = ({ title, onEdit }) => {
  return (
    <div className="flex justify-between items-center w-full">
      <span className="text-lg font-semibold truncate">{title}</span>
      <Menu as="div" className="relative inline-block text-left">
        <Menu.Button className="flex items-center p-2 text-gray-600 hover:text-gray-800">
          <Icon icon={EllipsisHorizontalIcon} />
        </Menu.Button>
        <Transition
          as={Fragment}
          enter="transition ease-out duration-100"
          enterFrom="transform opacity-0 scale-95"
          enterTo="transform opacity-100 scale-100"
          leave="transition ease-in duration-75"
          leaveFrom="transform opacity-100 scale-100"
          leaveTo="transform opacity-0 scale-95"
        >
          <Menu.Items className="absolute right-0 mt-2 w-56 origin-top-right bg-white divide-y divide-gray-100 rounded-md shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none z-50">
            <div className="px-1 py-1">
              <Menu.Item>
                {({ active }) => (
                  <Menu.Button
                    onClick={onEdit}
                    className={`${
                      active ? "bg-slate-200" : "text-gray-900"
                    } group flex w-full items-center rounded-md px-2 py-2 text-sm`}
                  >
                    <Subtitle>Edit</Subtitle>
                  </Menu.Button>
                )}
              </Menu.Item>
            </div>
          </Menu.Items>
        </Transition>
      </Menu>
    </div>
  );
};

export default Title;
