import { Menu, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { EllipsisHorizontalIcon } from "@heroicons/react/20/solid";
import { Icon } from "@tremor/react";
import {
  EyeIcon,
  PencilIcon,
  PlayIcon,
  TrashIcon,
  WrenchIcon,
} from "@heroicons/react/24/outline";
import {
  DownloadIcon,
  LockClosedIcon,
  LockOpen1Icon,
} from "@radix-ui/react-icons";
import React from "react";

interface WorkflowMenuProps {
  onDelete?: () => Promise<void>;
  onRun?: () => Promise<void>;
  onView?: () => void;
  onDownload?: () => void;
  onBuilder?: () => void;
  isRunButtonDisabled: boolean;
  runButtonToolTip?: string;
  provisioned?: boolean;
}

export default function WorkflowMenu({
  onDelete,
  onRun,
  onView,
  onDownload,
  onBuilder,
  isRunButtonDisabled,
  runButtonToolTip,
  provisioned,
}: WorkflowMenuProps) {
  const [showTooltip, setShowTooltip] = React.useState(false);
  const [tooltipPosition, setTooltipPosition] = React.useState({
    top: 0,
    left: 0,
  });
  const wrapperRef = React.useRef<HTMLDivElement>(null);
  const stopPropagation = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
  };

  const handleMouseEnter = () => {
    if (isRunButtonDisabled && runButtonToolTip && wrapperRef.current) {
      const rect = wrapperRef.current.getBoundingClientRect();
      setTooltipPosition({
        top: rect.top - 40,
        left: rect.left + rect.width / 2,
      });
      setShowTooltip(true);
    }
  };

  const handleMouseLeave = () => {
    setShowTooltip(false);
  };

  return (
    <div className="w-44 text-right">
      <Menu as="div" className="relative inline-block text-left z-10">
        <div>
          <Menu.Button
            className="inline-flex w-full justify-center rounded-md text-sm"
            onClick={stopPropagation}
          >
            <Icon
              size="sm"
              icon={EllipsisHorizontalIcon}
              className="hover:bg-gray-100 w-8 h-8" // you can manually adjust the size here
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
                  <div
                    ref={wrapperRef}
                    onMouseEnter={handleMouseEnter}
                    onMouseLeave={handleMouseLeave}
                    className="relative"
                  >
                    <button
                      disabled={isRunButtonDisabled}
                      onClick={(e) => {
                        stopPropagation(e);
                        onRun?.();
                      }}
                      className={`${
                        active ? "bg-slate-200" : "text-gray-900"
                      } flex w-full items-center rounded-md px-2 py-2 text-xs ${
                        isRunButtonDisabled
                          ? "cursor-not-allowed opacity-50"
                          : ""
                      }`}
                    >
                      <PlayIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                      Run
                    </button>
                  </div>
                )}
              </Menu.Item>
              <Menu.Item>
                {({ active }) => (
                  <button
                    onClick={(e) => {
                      stopPropagation(e);
                      onDownload?.();
                    }}
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
                    onClick={(e) => {
                      stopPropagation(e);
                      onView?.();
                    }}
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
                    onClick={(e) => {
                      stopPropagation(e);
                      onBuilder?.();
                    }}
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
                  <div className="relative group">
                    <button
                      disabled={provisioned}
                      onClick={(e) => {
                        stopPropagation(e);
                        onDelete?.();
                      }}
                      className={`${
                        active ? "bg-slate-200" : "text-gray-900"
                      } flex w-full items-center rounded-md px-2 py-2 text-xs ${
                        provisioned ? "cursor-not-allowed opacity-50" : ""
                      }`}
                    >
                      <TrashIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                      Delete
                    </button>
                    {provisioned && (
                      <div className="absolute bottom-full transform -translate-x-1/2 bg-black text-white text-xs rounded px-4 py-1 z-10 opacity-0 group-hover:opacity-100">
                        Cannot delete a provisioned workflow
                      </div>
                    )}
                  </div>
                )}
              </Menu.Item>
            </div>
          </Menu.Items>
        </Transition>
      </Menu>
      {showTooltip && isRunButtonDisabled && runButtonToolTip && (
        <div
          className="fixed bg-black text-white text-xs rounded px-4 py-1 z-50 transform -translate-x-1/2 whitespace-nowrap"
          style={{
            top: `${tooltipPosition.top}px`,
            left: `${tooltipPosition.left}px`,
          }}
        >
          {runButtonToolTip}
        </div>
      )}
    </div>
  );
}
