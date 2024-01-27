import React from 'react';
import { useForm, Controller, SubmitHandler, FieldValues } from 'react-hook-form';
import { Dialog } from "@headlessui/react";
import { TextInput, Button, Subtitle, SearchSelect, SearchSelectItem, Icon } from "@tremor/react";
import { AuthenticationType } from "utils/authenticationType";
import { User } from "./models";
import { getApiURL } from "utils/apiUrl";
import { InfoCircledIcon } from "@radix-ui/react-icons";

const roleOptions: RoleOption[] = [
  {
    value: "cli",
    label: "CLI",
    tooltip: "CLI has write alert ability",
  },
  {
    value: "create_new",
    label: "Create custom role",
    isDisabled: true,
    tooltip: "For custom roles, contact Keep team",
  },
];

export default function CreateApiKeyModal({ isOpen, onClose, apiUrl, setApiKeys, accessToken }: any) {
    const { handleSubmit, control, setError, clearErrors, reset, formState: { errors } } = useForm();

    const onSubmit: SubmitHandler<FieldValues> = async (data) => {
      try {
        const response = await fetch(`${apiUrl}/settings/apikey`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(data),
        });

        if (response.ok) {
          const newApiKey = await response.json();
          setApiKeys(prevApiKeys => [...prevApiKeys, newApiKey]);
          handleClose();
        } else {
          const errorData = await response.json();
          // if 'detail' in errorData:
          if (errorData.detail) {
            setError('apiError', { type: 'manual', message: errorData.detail });
          }
          else{
            setError('apiError', { type: 'manual', message: errorData.message || 'Failed to create API Key' });
          }

        }
      } catch (error) {
          console.log({error})
        setError('apiError', { type: 'manual', message: 'An unexpected error occurred' });
      }
    };

    const handleClose = () => {
        clearErrors('apiError');
        reset();
        onClose();
      };

    return (
      <Dialog as="div" className="fixed inset-0 z-10 overflow-y-auto" open={isOpen} onClose={handleClose}>
        <div className="flex items-center justify-center min-h-screen">
          <Dialog.Panel className="bg-white p-4 rounded" style={{ width: "400px", maxWidth: "90%" }}>
            <Dialog.Title>Add User</Dialog.Title>
            <form
                onSubmit={e => {
                    clearErrors()
                    handleSubmit(onSubmit)(e)
                }}
            >
              {/* Email/Username Field */}
              {
                <div className="mt-4">
                  <Subtitle>Name</Subtitle>
                  <Controller
                    name="name"
                    control={control}
                    rules={{ required: 'Name is required' }}
                    render={({ field }) => <TextInput {...field} error={!!errors.username} errorMessage={errors.username && typeof errors.username.message === 'string' ? errors.username.message : undefined}/>}
                  />
                </div>
              }

              {/* Role Field */}
              <div className="mt-4">
                <Subtitle>Role</Subtitle>
                <Controller
                    name="role"
                    control={control}
                    rules={{ required: 'Role is required' }}
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
                            {roleOptions.map(role => (
                            <SearchSelectItem
                                key={role.value}
                                value={role.value}
                                className={
                                role.isDisabled ? "text-gray-400 cursor-not-allowed" : ""
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
                        {errors.role && <div className="text-sm text-rose-500 mt-1">{errors.role.message?.toString()}</div>}
                        </>
                    )}
                    />

              </div>

              {/* Display API Error */}
              {errors.apiError && typeof errors.apiError.message === 'string' && (
                <div className="text-red-500 mt-2">{errors.apiError.message}</div>
              )}

              {/* Submit and Cancel Buttons */}
              <div className="mt-6 flex gap-2">
                <Button color="orange" type="submit">Create API Key </Button>
                <Button onClick={handleClose} variant="secondary" className="border border-orange-500 text-orange-500">Cancel</Button>
              </div>
            </form>
          </Dialog.Panel>
        </div>
      </Dialog>
    );
  }


