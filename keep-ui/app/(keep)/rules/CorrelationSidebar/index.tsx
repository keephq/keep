import { Fragment } from "react";
import { Dialog, Transition } from "@headlessui/react";
import { CorrelationSidebarHeader } from "./CorrelationSidebarHeader";
import { CorrelationSidebarBody } from "./CorrelationSidebarBody";
import { CorrelationFormType } from "./types";

export const DEFAULT_CORRELATION_FORM_VALUES: CorrelationFormType = {
  name: "",
  description: "",
  timeAmount: 24,
  timeUnit: "hours",
  groupedAttributes: [],
  requireApprove: false,
  resolveOn: "never",
  query: {
    combinator: "or",
    rules: [
      {
        combinator: "and",
        rules: [{ field: "source", operator: "=", value: "" }],
      },
      {
        combinator: "and",
        rules: [{ field: "source", operator: "=", value: "" }],
      },
    ],
  },
};

type CorrelationSidebarProps = {
  isOpen: boolean;
  toggle: VoidFunction;
  defaultValue?: CorrelationFormType;
};

export const CorrelationSidebar = ({
  isOpen,
  toggle,
  defaultValue = DEFAULT_CORRELATION_FORM_VALUES,
}: CorrelationSidebarProps) => (
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
        <Dialog.Panel className="fixed right-0 inset-y-0 min-w-12   bg-white z-30 p-6 overflow-auto flex flex-col">
          <CorrelationSidebarHeader toggle={toggle} />
          <CorrelationSidebarBody toggle={toggle} defaultValue={defaultValue} />
        </Dialog.Panel>
      </Transition.Child>
    </Dialog>
  </Transition>
);
