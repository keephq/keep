import { Menu, Transition } from "@headlessui/react";
import { Fragment, useEffect, useRef, useState } from "react";
import { Bars3Icon, ChevronDownIcon } from "@heroicons/react/20/solid";
import { Icon } from "@tremor/react";
import { TrashIcon } from "@radix-ui/react-icons";
import { ArrowPathIcon, PencilIcon } from "@heroicons/react/24/outline";
import { Provider } from "./providers";

interface Props {
  onDelete?: () => Promise<void>;
  onEdit?: () => void;
  onInstallWebhook?: () => Promise<void>;
  provider: Provider;
}

export default function ProviderMenu({
  onDelete,
  onEdit,
  onInstallWebhook,
  provider,
}: Props) {
  return (
    <div className="w-44 text-right">
      <Menu as="div" className="relative inline-block text-left">
        <div>
          <Menu.Button className="inline-flex w-full justify-center rounded-md text-sm">
            <Icon
              size="xs"
              icon={Bars3Icon}
              className="mr-2.5 hover:bg-gray-100"
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
                    disabled
                    className={`${
                      active ? "bg-slate-200" : "text-gray-900"
                    } group flex w-full items-center rounded-md px-2 py-2 text-xs text-slate-300 cursor-not-allowed`}
                  >
                    <PencilIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                    Edit
                  </button>
                )}
              </Menu.Item>
              <Menu.Item>
                {({ active }) => (
                  <button
                    className={`${
                      active ? "bg-slate-200" : "text-gray-900"
                    } group flex w-full items-center rounded-md px-2 py-2 text-xs ${
                      provider.can_setup_webhook
                        ? ""
                        : "text-slate-300 cursor-not-allowed"
                    }`}
                    onClick={onInstallWebhook}
                    disabled={!provider.can_setup_webhook}
                  >
                    <ArrowPathIcon
                      className="mr-2 h-4 w-4"
                      aria-hidden="true"
                    />
                    Install Webhook
                  </button>
                )}
              </Menu.Item>
            </div>
            <div className="px-1 py-1">
              <Menu.Item>
                {({ active }) => (
                  <button
                    onClick={onDelete}
                    className={`${
                      active ? "bg-slate-200" : "text-gray-900"
                    } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                  >
                    <TrashIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                    Delete
                  </button>
                )}
              </Menu.Item>
            </div>
          </Menu.Items>
        </Transition>
      </Menu>
    </div>
  );
}
