import { Fragment } from "react";
import { Dialog, Transition } from "@headlessui/react";
import { AlertDto } from "./models";
import { Button, Subtitle, Title } from "@tremor/react";
import { IoMdClose } from "react-icons/io";
import AlertMenu from "./alert-menu";

type AlertSidebarProps = {
  isOpen: boolean;
  toggle: VoidFunction;
  alert: AlertDto | null;
};

const AlertSidebar = ({ isOpen, toggle, alert }: AlertSidebarProps) => (
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
        <Dialog.Panel className="fixed right-0 inset-y-0 w-3/4 bg-white z-30 p-6 overflow-auto flex flex-col">
          <div className="flex justify-between">
            <div>
              <AlertMenu alert={alert} presetName="feed" isInSidebar={true} />
              <Dialog.Title className="text-3xl font-bold" as={Title}>
                Alert Details
              </Dialog.Title>
              <Dialog.Description as={Subtitle}>
                Details for the selected alert
              </Dialog.Description>
            </div>
            <div>
              <Button onClick={toggle} variant="light">
                <IoMdClose className="h-6 w-6 text-gray-500" />
              </Button>
            </div>
          </div>
          {alert && (
            <div className="mt-4">
              <p><strong>ID:</strong> {alert.id}</p>
              <p><strong>Name:</strong> {alert.name}</p>
              <p><strong>Severity:</strong> {alert.severity}</p>
              <p><strong>Source:</strong> {alert.source}</p>
              <p><strong>Description:</strong> {alert.description}</p>
              {/* Add more fields as necessary */}
            </div>
          )}
        </Dialog.Panel>
      </Transition.Child>
    </Dialog>
  </Transition>
);

export default AlertSidebar;
