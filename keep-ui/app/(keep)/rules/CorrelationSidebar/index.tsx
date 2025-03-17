import { Fragment } from "react";
import { Dialog, Transition } from "@headlessui/react";
import { CorrelationSidebarHeader } from "./CorrelationSidebarHeader";
import { CorrelationSidebarBody } from "./CorrelationSidebarBody";
import { CorrelationFormType } from "./types";
import { Drawer } from "@/shared/ui/Drawer";

export const DEFAULT_CORRELATION_FORM_VALUES: CorrelationFormType = {
  name: "",
  description: "",
  timeAmount: 24,
  timeUnit: "hours",
  groupedAttributes: [],
  requireApprove: false,
  resolveOn: "never",
  createOn: "any",
  incidentNameTemplate: "",
  incidentPrefix: "",
  multiLevel: false,
  multiLevelPropertyName: "",
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
  <Drawer
    isOpen={isOpen}
    onClose={toggle}
    className="fixed right-0 inset-y-0 min-w-12 bg-white p-6 overflow-auto flex flex-col"
  >
    <CorrelationSidebarHeader toggle={toggle} />
    <CorrelationSidebarBody toggle={toggle} defaultValue={defaultValue} />
  </Drawer>
);
