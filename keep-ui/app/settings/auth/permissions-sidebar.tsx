import { Fragment, useEffect } from "react";
import { Dialog, Transition } from "@headlessui/react";
import { Text, Button, Badge } from "@tremor/react";
import { IoMdClose } from "react-icons/io";
import { MultiSelect, MultiSelectItem } from "@tremor/react";
import { Permission } from "app/settings/models"; // Adjust the import as necessary

interface PermissionSidebarProps {
  isOpen: boolean;
  toggle: VoidFunction;
  accessToken: string;
  preset: any;
  permissions: Permission[];
  selectedPermissions: { [key: string]: string[] };
  onPermissionChange: (presetId: string, newPermissions: string[]) => void;
}

const PermissionSidebar = ({
  isOpen,
  toggle,
  accessToken,
  preset,
  permissions,
  selectedPermissions,
  onPermissionChange,
}: PermissionSidebarProps) => {
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
          <Dialog.Panel className="fixed right-0 inset-y-0 w-3/4 bg-white z-30 p-6 overflow-auto flex flex-col">
            <div className="flex justify-between mb-4">
              <Dialog.Title className="text-3xl font-bold" as={Text}>
                Permissions Details
              </Dialog.Title>
              <Button onClick={toggle} variant="light">
                <IoMdClose className="h-6 w-6 text-gray-500" />
              </Button>
            </div>
            {preset && (
              <div className="flex flex-col space-y-4">
                <div>
                  <Text className="text-lg font-medium">Resource Name</Text>
                  <Text>{preset.name}</Text>
                </div>
                <div>
                  <Text className="text-lg font-medium">Resource Type</Text>
                  <Text>{preset.type}</Text>
                </div>
                <div>
                  <Text className="text-lg font-medium">Permissions</Text>
                  <MultiSelect
                    placeholder="Select permissions"
                    value={selectedPermissions[preset.id] || []}
                    onValueChange={(value) => onPermissionChange(preset.id, value)}
                  >
                    {permissions.map((permission) => (
                      <MultiSelectItem key={permission.id} value={permission.id}>
                        {permission.name} ({permission.type})
                      </MultiSelectItem>
                    ))}
                  </MultiSelect>
                </div>
              </div>
            )}
          </Dialog.Panel>
        </Transition.Child>
      </Dialog>
    </Transition>
  );
};

export default PermissionSidebar;
