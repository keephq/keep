import { Menu, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { Bars3Icon, ChevronDownIcon } from "@heroicons/react/20/solid";
import { Icon } from "@tremor/react";
import { EyeIcon, PencilIcon, PlayIcon, TrashIcon, WrenchIcon } from "@heroicons/react/24/outline";
import { DownloadIcon } from "@radix-ui/react-icons";

interface WorkflowMenuProps {
  onDelete?: () => Promise<void>;
  onRun?: () => Promise<void>;
  onView?: () => void;
  onDownload?: () => void;
  onBuilder?: () => void;
  allProvidersInstalled: boolean;
  hasManualTrigger: boolean;

}


export default function WorkflowMenu({
  onDelete,
  onRun,
  onView,
  onDownload,
  onBuilder,
  allProvidersInstalled,
  hasManualTrigger,
}: WorkflowMenuProps) {
  const getDisabledTooltip = () => {
    if (!allProvidersInstalled) return "Not all providers are installed.";
    if (!hasManualTrigger) return "No manual trigger available.";
    return "";
  };
    const stopPropagation = (e: React.MouseEvent<HTMLButtonElement>) => {
        e.stopPropagation();
        };
      const isRunButtonDisabled = !allProvidersInstalled || !hasManualTrigger;
  return (
    <div className="w-44 text-right">
      <Menu as="div" className="relative inline-block text-left z-10">
        <div>
        <Menu.Button className="inline-flex w-full justify-center rounded-md text-sm" onClick={stopPropagation} >
        <Icon
            size="sm"
            icon={Bars3Icon}
            className="hover:bg-gray-100 w-8 h-8"  // you can manually adjust the size here
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
                <div className="relative group">
                  <button
                    disabled={isRunButtonDisabled}
                    onClick={(e) => { stopPropagation(e); onRun?.(); }}
                    className={`${
                      active ? 'bg-slate-200' : 'text-gray-900'
                    } flex w-full items-center rounded-md px-2 py-2 text-xs ${isRunButtonDisabled ? 'cursor-not-allowed opacity-50' : ''}`}
                  >
                    <PlayIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                    Run
                  </button>
                  {isRunButtonDisabled && (
                    <div className="absolute bottom-full transform -translate-x-1/2 bg-black text-white text-xs rounded px-4 py-1 z-10 opacity-0 group-hover:opacity-100">
                      {getDisabledTooltip()}
                    </div>
                  )}
                </div>
              )}
            </Menu.Item>
              <Menu.Item>
                {({ active }) => (
                  <button
                  onClick={(e) => { stopPropagation(e); onDownload?.(); }}
                    className={`${
                      active ? "bg-slate-200" : "text-gray-900"
                    } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                  >
                    <DownloadIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                    Download
                  </button>
                )}
              </Menu.Item>
              <Menu.Item>
                {({ active }) => (
                  <button
                  onClick={(e) => { stopPropagation(e); onView?.(); }}
                    className={`${
                      active ? "bg-slate-200" : "text-gray-900"
                    } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                  >
                    <EyeIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                    Last executions
                  </button>
                )}
              </Menu.Item>
              <Menu.Item>
                {({ active }) => (
                  <button
                    onClick={(e) => { stopPropagation(e); onBuilder?.();}}
                    className={`${
                      active ? "bg-slate-200" : "text-gray-900"
                    } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                  >
                    <WrenchIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                    Open in builder
                  </button>
                )}
              </Menu.Item>
              <Menu.Item>
                {({ active }) => (
                  <button
                  onClick={(e) => { stopPropagation(e); onDelete?.(); }}
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
