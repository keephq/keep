import { Fragment, useEffect, useState } from "react";
import { Dialog, Transition } from "@headlessui/react";
import { useForm, Controller, SubmitHandler, FieldValues } from "react-hook-form";
import { Text, Button, TextInput, Callout, Badge } from "@tremor/react";
import { IoMdClose } from "react-icons/io";

interface RoleSidebarProps {
  isOpen: boolean;
  toggle: VoidFunction;
  accessToken: string;
  selectedRole: any;
  resources: string[];
  mutateRoles: () => void;
}

const RoleSidebar = ({
  isOpen,
  toggle,
  accessToken,
  selectedRole,
  resources,
  mutateRoles,
}: RoleSidebarProps) => {
  const { control, handleSubmit, setValue, reset: resetForm, setError, formState: { errors }, clearErrors } = useForm({
    defaultValues: {
      name: "",
      description: "",
    },
  });

  const [newRoleScopes, setNewRoleScopes] = useState<{ [key: string]: any }>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (selectedRole) {
      setValue("name", selectedRole.name);
      setValue("description", selectedRole.description);
      const roleScopes = selectedRole.scopes.reduce((acc: any, scope: string) => {
        const [action, resource] = scope.split(":");
        if (!acc[resource]) acc[resource] = {};
        acc[resource][action] = true;
        return acc;
      }, {});
      setNewRoleScopes(roleScopes);
    } else {
      resetForm();
      setNewRoleScopes({});
    }
  }, [selectedRole, setValue, resetForm]);

  const prepopulateScopes = () => {
    return resources.map((resource) => (
      <Fragment key={resource}>
        <Text>{resource}</Text>
        {["read", "write", "delete", "update"].map((action) => (
          <div
            key={action}
            className={`flex items-center justify-center cursor-pointer ${
              newRoleScopes[resource]?.[action] ? "text-green-500" : "text-gray-300"
            }`}
            onClick={() => {
              if (!selectedRole || !selectedRole.predefined) {
                setNewRoleScopes((prev) => ({
                  ...prev,
                  [resource]: {
                    ...prev[resource],
                    [action]: !prev[resource]?.[action],
                  },
                }));
              }
            }}
          >
            {newRoleScopes[resource]?.[action] ? (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            )}
          </div>
        ))}
      </Fragment>
    ));
  };

  const onSubmit: SubmitHandler<FieldValues> = async (data) => {
    setIsSubmitting(true);
    clearErrors();
    try {
      const newRole = {
        ...data,
        scopes: Object.entries(newRoleScopes)
          .filter(([_, actions]) => Object.values(actions).some(Boolean))
          .flatMap(([resource, actions]) =>
            Object.entries(actions)
              .filter(([_, value]) => value)
              .map(([action, _]) => `${action}:${resource}`)
          ),
      };

      const response = await fetch(`${apiUrl}/auth/roles`, {
        method: selectedRole ? "PUT" : "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(newRole),
      });

      if (response.ok) {
        console.log("Role saved:", newRole);
        resetForm();
        toggle();
        await mutateRoles();
      } else {
        const errorData = await response.json();
        setError("apiError", { type: "manual", message: errorData.message || "Failed to save role" });
      }
    } catch (error) {
      setError("apiError", { type: "manual", message: "An unexpected error occurred" });
    } finally {
      setIsSubmitting(false);
    }
  };

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
                {selectedRole ? "Edit Role" : "Add Role"}
                <Badge className="ml-4" color="orange">Beta</Badge>
                {selectedRole && selectedRole.predefined && (
                  <Badge className="ml-2" color="orange">Predefined Role</Badge>
                )}
              </Dialog.Title>
              <Button onClick={toggle} variant="light">
                <IoMdClose className="h-6 w-6 text-gray-500" />
              </Button>
            </div>
            <form onSubmit={handleSubmit(onSubmit)} className="mt-4 flex flex-col h-full">
              <div className="flex-grow">
                <div className="mt-4">
                  <label className="block text-sm font-medium text-gray-700">
                    Role Name
                  </label>
                  <Controller
                    name="name"
                    control={control}
                    rules={{ required: "Role name is required" }}
                    render={({ field }) => (
                      <TextInput
                        {...field}
                        error={!!errors.name}
                        errorMessage={errors.name?.message}
                        disabled={selectedRole && selectedRole.predefined}
                        className={`${
                          selectedRole && selectedRole.predefined ? "bg-gray-200" : ""
                        }`}
                      />
                    )}
                  />
                </div>
                <div className="mt-4">
                  <label className="block text-sm font-medium text-gray-700">
                    Description
                  </label>
                  <Controller
                    name="description"
                    control={control}
                    rules={{ required: "Description is required" }}
                    render={({ field }) => (
                      <TextInput
                        {...field}
                        error={!!errors.description}
                        errorMessage={errors.description?.message}
                        disabled={selectedRole && selectedRole.predefined}
                        className={`${
                          selectedRole && selectedRole.predefined ? "bg-gray-200" : ""
                        }`}
                      />
                    )}
                  />
                </div>
                <div className="mt-4">
                  <Text>Scopes</Text>
                  <div className="grid grid-cols-5 gap-4 mt-2">
                    <div></div>
                    <Text>Read</Text>
                    <Text>Write</Text>
                    <Text>Delete</Text>
                    <Text>Update</Text>
                    {prepopulateScopes()}
                  </div>
                </div>
                {errors.apiError && typeof errors.apiError.message === "string" && (
                  <Callout className="mt-4" title="Error while adding role" color="rose">
                    {errors.apiError.message}
                  </Callout>
                )}
              </div>
              <div className="mt-6 flex justify-end gap-2">
                <Button
                  color="orange"
                  variant="secondary"
                  onClick={() => {
                    resetForm();
                    toggle();
                  }}
                  className="border border-orange-500 text-orange-500"
                >
                  Cancel
                </Button>
                {!selectedRole?.predefined && (
                  <Button
                    color="orange"
                    type="submit"
                    disabled={isSubmitting || !Object.values(newRoleScopes).some(scope => Object.values(scope).some(Boolean))}
                    title={!newRoleScopes ? "At least one scope must be selected" : ""}
                  >
                    {isSubmitting ? "Saving..." : "Save Role"}
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

export default RoleSidebar;
