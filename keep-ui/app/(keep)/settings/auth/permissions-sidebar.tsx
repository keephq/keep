import { Fragment, useEffect } from "react";
import { Dialog, Transition } from "@headlessui/react";
import {
  Text,
  Button,
  Badge,
  MultiSelect,
  MultiSelectItem,
  Callout,
  Title,
  Subtitle,
} from "@tremor/react";
import { IoMdClose } from "react-icons/io";
import { User, Group, Role } from "@/app/(keep)/settings/models";
import {
  useForm,
  Controller,
  SubmitHandler,
  FieldValues,
} from "react-hook-form";
import "./multiselect.css";

interface PermissionSidebarProps {
  isOpen: boolean;
  toggle: VoidFunction;
  selectedResource: any;
  entityOptions: {
    user: User[];
    group: Group[];
    role: Role[];
  };
  onSavePermissions: (
    resourceId: string,
    assignments: string[]
  ) => Promise<void>;
  isDisabled?: boolean;
}

const PermissionSidebar = ({
  isOpen,
  toggle,
  selectedResource,
  entityOptions,
  onSavePermissions,
  isDisabled = false,
}: PermissionSidebarProps) => {
  const {
    control,
    handleSubmit,
    setValue,
    reset,
    formState: { errors, isDirty },
    clearErrors,
    setError,
  } = useForm({
    defaultValues: {
      assignments: [],
    },
  });

  useEffect(() => {
    if (isOpen && selectedResource) {
      setValue("assignments", selectedResource.assignments || []);
      clearErrors();
    }
  }, [selectedResource, setValue, isOpen, clearErrors]);

  const getAllEntityOptions = () => {
    const options = [];

    for (const user of entityOptions.user) {
      options.push({
        id: `user-${user.email}`,
        label: `${user.email || user.name} (User)`,
        value: `user_${user.email}`, // Format: type_id
      });
    }

    for (const group of entityOptions.group) {
      options.push({
        id: `group-${group.id}`,
        label: `${group.name} (Group)`,
        value: `group_${group.name}`, // Format: type_id
      });
    }
    /* Support roles in the future
    for (const role of entityOptions.role) {
      options.push({
        id: `role-${role.id}`,
        label: `${role.name} (Role)`,
        value: `role_${role.id}`, // Format: type_id
      });
    }
    */

    return options;
  };

  const onSubmit: SubmitHandler<FieldValues> = async (data) => {
    try {
      await onSavePermissions(selectedResource.id, data.assignments);
      handleClose();
    } catch (error) {
      setError("root.serverError", {
        message: "Failed to save permissions",
      });
    }
  };

  const handleClose = () => {
    clearErrors();
    reset();
    toggle();
  };

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog onClose={handleClose}>
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
                Manage Permissions
                <Badge className="ml-4" color="orange">
                  Beta
                </Badge>
              </Dialog.Title>
              <Button onClick={handleClose} variant="light">
                <IoMdClose className="h-6 w-6 text-gray-500" />
              </Button>
            </div>

            <form
              onSubmit={handleSubmit(onSubmit)}
              className="mt-4 flex flex-col h-full"
            >
              <div className="flex-grow">
                <div className="mt-8">
                  <Title className="mb-2">Resource</Title>
                  <Text className="text-gray-900">
                    {selectedResource?.name}
                  </Text>
                </div>

                <div className="mt-6">
                  <Title className="mb-2">Type</Title>
                  <Badge color="orange" size="lg">
                    {selectedResource?.type}
                  </Badge>
                </div>

                <div className="mt-6">
                  <Title className="mb-2">Assign To</Title>
                  <Controller
                    name="assignments"
                    control={control}
                    render={({ field }) => (
                      <MultiSelect
                        {...field}
                        onValueChange={(value) => field.onChange(value)}
                        value={field.value as string[]}
                        className="custom-multiselect"
                        disabled={isDisabled}
                      >
                        {getAllEntityOptions().map((option) => (
                          <MultiSelectItem key={option.id} value={option.value}>
                            {option.label}
                          </MultiSelectItem>
                        ))}
                      </MultiSelect>
                    )}
                  />
                </div>
              </div>

              {errors.root?.serverError && (
                <Callout
                  className="mt-4"
                  title="Error while saving permissions"
                  color="rose"
                >
                  {errors.root.serverError.message}
                </Callout>
              )}

              <div className="mt-6 flex justify-end gap-3">
                <Button
                  color="orange"
                  variant="secondary"
                  onClick={handleClose}
                  className="border border-orange-500 text-orange-500"
                >
                  Cancel
                </Button>
                {!isDisabled && (
                  <Button color="orange" type="submit" disabled={!isDirty}>
                    Save Changes
                  </Button>
                )}
              </div>
            </form>
          </Dialog.Panel>
        </Transition.Child>
      </Dialog>
    </Transition>
  );
};

export default PermissionSidebar;
