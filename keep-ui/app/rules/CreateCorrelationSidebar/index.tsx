import { Dialog } from "@headlessui/react";
import { CreateCorrelationSidebarHeader } from "./CreateCorrelationSidebarHeader";
import { CreateCorrelationSidebearBody } from "./CreateCorrelationSidebarBody";

type CreateCorrelationSidebarProps = {
  isOpen: boolean;
  toggle: VoidFunction;
};

export const CreateCorrelationSidebar = ({
  isOpen,
  toggle,
}: CreateCorrelationSidebarProps) => {
  return (
    <Dialog open={isOpen} onClose={toggle}>
      <div className="fixed inset-0 bg-black/30 z-20" aria-hidden="true" />
      <Dialog.Panel className="fixed right-0 inset-y-0 w-3/4 bg-white z-30 p-6">
        <CreateCorrelationSidebarHeader toggle={toggle} />
        <CreateCorrelationSidebearBody />
      </Dialog.Panel>
    </Dialog>
  );
};
