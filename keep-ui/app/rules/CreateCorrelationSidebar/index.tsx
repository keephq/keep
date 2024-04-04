import { Dialog, Transition } from "@headlessui/react";
import { CreateCorrelationSidebarHeader } from "./CreateCorrelationSidebarHeader";
import { CreateCorrelationSidebarBody } from "./CreateCorrelationSidebarBody";
import { Fragment } from "react";

type CreateCorrelationSidebarProps = {
  isOpen: boolean;
  toggle: VoidFunction;
};

export const CreateCorrelationSidebar = ({
  isOpen,
  toggle,
}: CreateCorrelationSidebarProps) => {
  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog onClose={toggle}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/30 z-20" aria-hidden="true" />
        </Transition.Child>
        <Transition.Child
          as={Fragment}
          enter="transition ease-in-out duration-300 transform"
          enterFrom="translate-x-full"
          enterTo="translate-x-0"
          leave="transition ease-in-out duration-300 transform"
          leaveFrom="translate-x-0"
          leaveTo="translate-x-full"
        >
          <Dialog.Panel className="fixed right-0 inset-y-0 w-3/4 bg-white z-30 p-6 overflow-auto">
            <CreateCorrelationSidebarHeader toggle={toggle} />
            <CreateCorrelationSidebarBody />
          </Dialog.Panel>
        </Transition.Child>
      </Dialog>
    </Transition>
  );
};
