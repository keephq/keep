import { Fragment, useEffect, useState } from "react";
import { Dialog, Transition } from "@headlessui/react";
import {
  Text,
  Button,
  Badge,
  TextInput,
  MultiSelect,
  MultiSelectItem,
  Callout,
} from "@tremor/react";
import { IoMdClose } from "react-icons/io";
import {
  useForm,
  Controller,
  SubmitHandler,
  FieldValues,
} from "react-hook-form";
import { Permission, User, Group, Role } from "app/settings/models";

interface PermissionSidebarProps {
  isOpen: boolean;
  toggle: VoidFunction;
  accessToken: string;
  selectedPermission: Permission | null;
  resourceTypes: string[];
  resources: { [key: string]: any[] };
  entityOptions: {
    user: User[];
    group: Group[];
    role: Role[];
  };
  onSavePermission: (permissionData: any) => Promise<void>;
  isDisabled?: boolean;
}

const PermissionSidebar = ({
  isOpen,
  toggle,
  accessToken,
  selectedPermission,
  resourceTypes,
  resources,
  entityOptions,
  onSavePermission,
  isDisabled = false,
}: PermissionSidebarProps) => {
  const {
    control,
    handleSubmit,
    setValue,
    reset,
    watch,
    formState: { errors, isDirty },
    clearErrors,
    setError,
  } = useForm({
    defaultValues: {
      resourceType: "",
      resourceId: "",
      entity: "",
    },
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const selectedResourceType = watch("resourceType");

  // Combine all entity options into a single array with type labels
  const getAllEntityOptions = () => {
    const options = [];

    for (const user of entityOptions.user) {
      options.push({
        id: `user-${user.name || user.email}`,
        label: `${user.name || user.email} (User)`,
        value: `user_${user.name || user.email}`,
      });
    }

    for (const group of entityOptions.group) {
      options.push({
        id: `group-${group.id}`,
        label: `${group.name} (Group)`,
        value: `group_${group.id}`,
      });
    }

    for (const role of entityOptions.role) {
      options.push({
        id: `role-${role.id}`,
        label: `${role.name} (Role)`,
        value: `role_${role.id}`,
      });
    }

    return options;
  };

  useEffect(() => {
    if (isOpen) {
      if (selectedPermission) {
        setValue("resourceType", selectedPermission.type);
        setValue("resourceId", selectedPermission.resource_id);
        setValue("entity", selectedPermission.entity_id);
      } else {
        reset({
          resourceType: "",
          resourceId: "",
          entity: "",
        });
      }
      clearErrors();
    }
  }, [selectedPermission, setValue, isOpen, reset, clearErrors]);

  const onSubmit: SubmitHandler<FieldValues> = async (data) => {
    setIsSubmitting(true);
    clearErrors();

    try {
      await onSavePermission({
        type: data.resourceType,
        resource_id: data.resourceId,
        entity_id: data.entity,
      });
      handleClose();
    } catch (error) {
      setError("root.serverError", {
        message: "Failed to save permission",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    setIsSubmitting(false);
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
                {selectedPermission ? "Edit Permission" : "Add Permission"}
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
                <div className="mt-4">
                  <label className="block text-sm font-medium text-gray-700">
                    Resource Type
                  </label>
                  <Controller
                    name="resourceType"
                    control={control}
                    rules={{ required: "Resource type is required" }}
                    render={({ field }) => (
                      <MultiSelect
                        value={field.value ? [field.value] : []}
                        onValueChange={(value) => {
                          if (value.length > 0) {
                            field.onChange(value[0]);
                            // Reset resourceId when type changes
                            setValue("resourceId", "");
                          }
                        }}
                        className="custom-multiselect"
                        disabled={isDisabled || !!selectedPermission}
                      >
                        {resourceTypes.map((type) => (
                          <MultiSelectItem key={`type-${type}`} value={type}>
                            {type}
                          </MultiSelectItem>
                        ))}
                      </MultiSelect>
                    )}
                  />
                </div>

                {selectedResourceType && (
                  <div className="mt-4">
                    <label className="block text-sm font-medium text-gray-700">
                      Resource
                    </label>
                    <Controller
                      name="resourceId"
                      control={control}
                      rules={{ required: "Resource is required" }}
                      render={({ field }) => (
                        <MultiSelect
                          value={field.value ? [field.value] : []}
                          onValueChange={(value) => {
                            if (value.length > 0) {
                              field.onChange(value[0]);
                            }
                          }}
                          className="custom-multiselect"
                          disabled={isDisabled || !!selectedPermission}
                        >
                          {resources[selectedResourceType]?.map((resource) => (
                            <MultiSelectItem
                              key={`resource-${resource.id}`}
                              value={resource.id}
                            >
                              {resource.name}
                            </MultiSelectItem>
                          ))}
                        </MultiSelect>
                      )}
                    />
                  </div>
                )}

                <div className="mt-4">
                  <label className="block text-sm font-medium text-gray-700">
                    Assign To
                  </label>
                  <Controller
                    name="entity"
                    control={control}
                    rules={{ required: "Assignment is required" }}
                    render={({ field }) => (
                      <MultiSelect
                        value={field.value ? [field.value] : []}
                        onValueChange={(value) => {
                          if (value.length > 0) {
                            field.onChange(value[0]);
                          }
                        }}
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
                  title="Error while saving permission"
                  color="rose"
                >
                  {errors.root.serverError.message}
                </Callout>
              )}

              <div className="mt-6 flex justify-end gap-2">
                <Button
                  color="orange"
                  variant="secondary"
                  onClick={handleClose}
                  className="border border-orange-500 text-orange-500"
                >
                  Cancel
                </Button>
                {!isDisabled && (
                  <Button
                    color="orange"
                    type="submit"
                    disabled={isSubmitting || !isDirty}
                  >
                    {isSubmitting ? "Saving..." : "Save Permission"}
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
