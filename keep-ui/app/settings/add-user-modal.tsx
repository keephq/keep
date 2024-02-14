import React from "react";
import {
  useForm,
  Controller,
  SubmitHandler,
  FieldValues,
} from "react-hook-form";
import { Dialog } from "@headlessui/react";
import {
  TextInput,
  Button,
  Subtitle,
  SearchSelect,
  SearchSelectItem,
  Icon,
} from "@tremor/react";
import { AuthenticationType } from "utils/authenticationType";
import { User } from "./models";
import { getApiURL } from "utils/apiUrl";
import { InfoCircledIcon } from "@radix-ui/react-icons";
import "./add-user-modal.css";
import Modal from "@/components/ui/Modal";

interface RoleOption {
  value: string;
  label: string | JSX.Element;
  tooltip?: string;
  isDisabled?: boolean;
}

interface AddUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  authType: string;
  setUsers: React.Dispatch<React.SetStateAction<User[]>>;
  accessToken: string;
}

const roleOptions: RoleOption[] = [
  {
    value: "admin",
    label: "Admin",
    tooltip: "Admin has read/write/update/delete for every resource",
  },
  {
    value: "noc",
    label: "NOC",
    tooltip: "NOC has the ability to view and assign alerts",
  },
  {
    value: "create_new",
    label: "Create custom role",
    isDisabled: true,
    tooltip: "For custom roles, contact Keep team",
  },
];

export default function AddUserModal({
  isOpen,
  onClose,
  authType,
  setUsers,
  accessToken,
}: AddUserModalProps) {
  const {
    handleSubmit,
    control,
    setError,
    clearErrors,
    reset,
    formState: { errors },
  } = useForm();

  const onSubmit: SubmitHandler<FieldValues> = async (data) => {
    try {
      const response = await fetch(`${getApiURL()}/users`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      });

      if (response.ok) {
        const newUser = await response.json();
        setUsers((prevUsers) => [...prevUsers, newUser]);
        handleClose();
      } else {
        const errorData = await response.json();
        // if 'detail' in errorData:
        if (errorData.detail) {
          setError("apiError", { type: "manual", message: errorData.detail });
        } else {
          setError("apiError", {
            type: "manual",
            message: errorData.message || "Failed to add user",
          });
        }
      }
    } catch (error) {
      setError("apiError", {
        type: "manual",
        message: "An unexpected error occurred",
      });
    }
  };

  const handleClose = () => {
    clearErrors("apiError");
    reset();
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      className="w-[400px]"
      title="Add User"
    >
      <form
        onSubmit={(e) => {
          clearErrors();
          handleSubmit(onSubmit)(e);
        }}
      >
        {/* Email/Username Field */}
        {authType === AuthenticationType.MULTI_TENANT ? (
          <div className="mt-4">
            <Subtitle>Email</Subtitle>
            <Controller
              name="email"
              control={control}
              rules={{
                required: "Email is required",
                pattern: {
                  value: /\S+@\S+\.\S+/,
                  message: "Invalid email format",
                },
              }}
              render={({ field }) => (
                <>
                  <TextInput
                    {...field}
                    error={!!errors.email}
                    errorMessage={
                      errors.email && typeof errors.email.message === "string"
                        ? errors.email.message
                        : undefined
                    }
                  />
                </>
              )}
            />
          </div>
        ) : (
          <div className="mt-4">
            <Subtitle>Username</Subtitle>
            <Controller
              name="username"
              control={control}
              rules={{ required: "Username is required" }}
              render={({ field }) => (
                <TextInput
                  {...field}
                  error={!!errors.username}
                  errorMessage={
                    errors.username &&
                    typeof errors.username.message === "string"
                      ? errors.username.message
                      : undefined
                  }
                />
              )}
            />
          </div>
        )}

        {/* Role Field */}
        <div className="mt-4">
          <Subtitle>Role</Subtitle>
          <Controller
            name="role"
            control={control}
            rules={{ required: "Role is required" }}
            render={({ field: { onChange, value, ref } }) => (
              <>
                <SearchSelect
                  placeholder="Select role"
                  value={value}
                  onValueChange={onChange}
                  className={`rounded-lg border ${
                    errors.role ? "border-red-500" : "border-transparent"
                  }`}
                  ref={ref}
                >
                  {roleOptions.map((role) => (
                    <SearchSelectItem
                      key={role.value}
                      value={role.value}
                      className={
                        role.isDisabled
                          ? "text-gray-400 cursor-not-allowed"
                          : ""
                      }
                      onClick={(e) => {
                        if (role.isDisabled) {
                          e.preventDefault();
                        }
                      }}
                    >
                      <div className="flex items-center">
                        {role.label}
                        {role.tooltip && (
                          <Icon
                            icon={InfoCircledIcon}
                            className="role-tooltip"
                            tooltip={role.tooltip}
                            color="gray"
                            size="xs"
                          />
                        )}
                      </div>
                    </SearchSelectItem>
                  ))}
                </SearchSelect>
                {errors.role && (
                  <div className="text-sm text-rose-500 mt-1">
                    {errors.role.message?.toString()}
                  </div>
                )}
              </>
            )}
          />
        </div>

        {/* Password Field */}
        {authType === AuthenticationType.SINGLE_TENANT && (
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

        {/* Display API Error */}
        {errors.apiError && typeof errors.apiError.message === "string" && (
          <div className="text-red-500 mt-2">{errors.apiError.message}</div>
        )}

        {/* Submit and Cancel Buttons */}
        <div className="mt-6 flex gap-2">
          <Button color="orange" type="submit">
            Add User
          </Button>
          <Button
            onClick={handleClose}
            variant="secondary"
            className="border border-orange-500 text-orange-500"
          >
            Cancel
          </Button>
        </div>
      </form>
    </Modal>
  );
}
