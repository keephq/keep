import { Fragment, useEffect, useState } from "react";
import { Dialog, Transition } from "@headlessui/react";
import {
  Text,
  Subtitle,
  Button,
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
import { useRoles } from "utils/hooks/useRoles";
import { useGroups } from "utils/hooks/useGroups";
import { User, Group } from "@/app/(keep)/settings/models";
import { AuthType } from "utils/authenticationType";
import { useConfig } from "utils/hooks/useConfig";
import Select from "@/components/ui/Select";
import { KeepApiError } from "@/shared/api/KeepApiError";
import { useApi } from "@/shared/lib/hooks/useApi";

interface UserSidebarProps {
  isOpen: boolean;
  toggle: VoidFunction;
  user?: User;
  isNewUser: boolean;
  mutateUsers: (data?: any, shouldRevalidate?: boolean) => Promise<any>;
  groupsEnabled?: boolean;
  identifierType: "email" | "username";
  userCreationAllowed: boolean;
}

const UsersSidebar = ({
  isOpen,
  toggle,
  user,
  isNewUser,
  mutateUsers,
  groupsEnabled = true,
  identifierType,
  userCreationAllowed,
}: UserSidebarProps) => {
  const {
    control,
    handleSubmit,
    setValue,
    reset,
    formState: { errors, isDirty },
    clearErrors,
    setError,
  } = useForm<{
    username: string;
    name: string;
    role: string;
    groups: string[];
    password: string;
  }>({
    defaultValues: {
      username: "",
      name: "",
      role: "",
      groups: [],
      password: "",
    },
  });

  const api = useApi();
  const { data: roles = [] } = useRoles();
  const { data: groups = [], mutate: mutateGroups } = useGroups();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { data: configData } = useConfig();
  const authType = configData?.AUTH_TYPE as AuthType;

  useEffect(() => {
    if (isOpen) {
      if (user) {
        if (identifierType === "email") {
          // server parse as email
          setValue("username", user.email);
          setValue("name", user.name);
        } else {
          setValue("username", user.email || user.name);
        }
        setValue("role", user.role || "");
        setValue("groups", user.groups?.map((group: Group) => group.id) || []);
      } else {
        reset({
          username: "",
          name: "",
          role: "",
          groups: [],
        });
      }
      clearErrors(); // Clear errors when the modal is opened
    }
  }, [user, setValue, isOpen, reset, clearErrors, identifierType]);

  const onSubmit: SubmitHandler<FieldValues> = async (data) => {
    if (!userCreationAllowed) {
      return;
    }

    setIsSubmitting(true);
    clearErrors("root.serverError");

    const method = isNewUser ? "post" : "put";
    const url = isNewUser
      ? "/auth/users"
      : `/auth/users/${identifierType === "email" ? user?.email : user?.name}`;
    try {
      await api[method](url, data);

      await mutateUsers();
      await mutateGroups();
      handleClose();
    } catch (error) {
      if (error instanceof KeepApiError) {
        setError("root.serverError", {
          type: "manual",
          message: error.message || "Failed to save user",
        });
      } else {
        setError("root.serverError", {
          type: "manual",
          message: "An unexpected error occurred",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitClick = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userCreationAllowed) return;
    clearErrors(); // Clear errors on each submit click
    handleSubmit(onSubmit)();
  };

  const handleClose = () => {
    setIsSubmitting(false); // Ensure isSubmitting is reset when closing the modal
    clearErrors("root.serverError");
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
                {isNewUser ? "Create User" : "User Details"}
              </Dialog.Title>
              <Button onClick={handleClose} variant="light">
                <IoMdClose className="h-6 w-6 text-gray-500" />
              </Button>
            </div>
            <form
              onSubmit={handleSubmitClick}
              className="mt-4 flex flex-col h-full"
            >
              <div className="flex-grow">
                {!userCreationAllowed && (
                  <Callout
                    className="mt-4"
                    title="Users are managed externally"
                    color="orange"
                  >
                    User management is handled through your external
                    authentication system.
                  </Callout>
                )}
                {identifierType === "email" ? (
                  <>
                    <div className="mt-4">
                      <label className="block text-sm font-medium text-gray-700">
                        Email
                      </label>
                      <Controller
                        name="username"
                        control={control}
                        rules={{
                          required: "Email is required",
                          pattern: {
                            value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                            message: "Invalid email address",
                          },
                        }}
                        render={({ field }) => (
                          <TextInput
                            {...field}
                            error={!!errors.username}
                            errorMessage={errors.username?.message}
                            disabled={!isNewUser || !userCreationAllowed}
                            className="bg-gray-200"
                          />
                        )}
                      />
                    </div>
                    <div className="mt-4">
                      <label className="block text-sm font-medium text-gray-700">
                        Name
                      </label>
                      <Controller
                        name="name"
                        control={control}
                        rules={{ required: "Name is required" }}
                        render={({ field }) => (
                          <TextInput
                            {...field}
                            error={!!errors.name}
                            errorMessage={errors.name?.message}
                            disabled={!isNewUser || !userCreationAllowed}
                            className="bg-gray-200"
                          />
                        )}
                      />
                    </div>
                  </>
                ) : (
                  <div className="mt-4">
                    <label className="block text-sm font-medium text-gray-700">
                      Username
                    </label>
                    <Controller
                      name="username"
                      control={control}
                      rules={{ required: "Username is required" }}
                      render={({ field }) => (
                        <TextInput
                          {...field}
                          error={!!errors.username}
                          errorMessage={errors.username?.message}
                          disabled={!isNewUser || !userCreationAllowed}
                          className="bg-gray-200"
                        />
                      )}
                    />
                  </div>
                )}
                {/* Password Field */}
                {(authType === AuthType.DB || authType === AuthType.KEYCLOAK) &&
                  isNewUser &&
                  userCreationAllowed && (
                    <div className="mt-4">
                      <Subtitle>Password</Subtitle>
                      <Controller
                        name="password"
                        control={control}
                        rules={{ required: "Password is required" }}
                        render={({ field }) => (
                          <TextInput
                            type="password"
                            {...field}
                            error={!!errors.password}
                            errorMessage={
                              errors.password &&
                              typeof errors.password.message === "string"
                                ? errors.password.message
                                : undefined
                            }
                          />
                        )}
                      />
                    </div>
                  )}
                <div className="mt-4">
                  <label className="block text-sm font-medium text-gray-700">
                    Role
                  </label>
                  <Controller
                    name="role"
                    control={control}
                    render={({ field }) => (
                      <Select
                        {...field}
                        onChange={(selectedOption) =>
                          field.onChange(selectedOption?.name)
                        }
                        value={roles.find((role) => role.name === field.value)}
                        options={roles}
                        getOptionLabel={(role) => role.name}
                        getOptionValue={(role) => role.name}
                        placeholder="Select a role"
                        isDisabled={!userCreationAllowed}
                      />
                    )}
                  />
                </div>
                {groupsEnabled && (
                  <div className="mt-4">
                    <label className="block text-sm font-medium text-gray-700">
                      Groups
                    </label>
                    <Controller
                      name="groups"
                      control={control}
                      render={({ field }) => (
                        <MultiSelect
                          {...field}
                          onValueChange={(value) => field.onChange(value)}
                          value={field.value as string[]}
                          className="custom-multiselect"
                          disabled={!userCreationAllowed}
                        >
                          {groups.map((group) => (
                            <MultiSelectItem key={group.id} value={group.id}>
                              {group.name}
                            </MultiSelectItem>
                          ))}
                        </MultiSelect>
                      )}
                    />
                  </div>
                )}
              </div>
              {/* Display API Error */}
              {errors.root?.serverError && (
                <Callout
                  className="mt-4"
                  title="Error while saving user"
                  color="rose"
                >
                  {errors.root.serverError.message}
                </Callout>
              )}
              <div className="mt-6 flex justify-end gap-2">
                <Button
                  color="orange"
                  variant="secondary"
                  onClick={(e) => {
                    e.preventDefault();
                    handleClose();
                  }}
                  className="border border-orange-500 text-orange-500"
                >
                  Close
                </Button>
                {userCreationAllowed && (
                  <Button
                    color="orange"
                    type="submit"
                    disabled={isSubmitting || (isNewUser ? false : !isDirty)}
                  >
                    {isSubmitting
                      ? "Saving..."
                      : isNewUser
                        ? "Create User"
                        : "Save"}
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

export default UsersSidebar;
