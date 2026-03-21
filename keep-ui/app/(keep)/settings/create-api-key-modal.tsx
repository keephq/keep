import React from "react";
import {
  useForm,
  Controller,
  SubmitHandler,
  FieldValues,
} from "react-hook-form";
import { TextInput, Button, Subtitle, Icon } from "@tremor/react";
import { InfoCircledIcon } from "@radix-ui/react-icons";
import { Role } from "@/app/(keep)/settings/models";
import Modal from "@/components/ui/Modal";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/api";
import { ApiKey } from "@/app/(keep)/settings/auth/types";
import { Select } from "@/shared/ui";
import { useI18n } from "@/i18n/hooks/useI18n";
interface CreateApiKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
  setApiKeys: React.Dispatch<React.SetStateAction<ApiKey[]>>;
  roles: Role[];
}

export default function CreateApiKeyModal({
  isOpen,
  onClose,
  setApiKeys,
  roles,
}: CreateApiKeyModalProps) {
  const { t } = useI18n();
  const {
    handleSubmit,
    control,
    setError,
    clearErrors,
    reset,
    formState: { errors },
  } = useForm();

  const api = useApi();

  const onSubmit: SubmitHandler<FieldValues> = async (data) => {
    try {
      const newApiKey = await api.post("/settings/apikey", data);

      setApiKeys((prevApiKeys: ApiKey[]) => [...prevApiKeys, newApiKey]);
      handleClose();
    } catch (error) {
      if (error instanceof KeepApiError) {
        setError("apiError", {
          type: "manual",
          message: error.message || t("settings.apiKeys.messages.createFailed"),
        });
      } else {
        setError("apiError", {
          type: "manual",
          message: t("apiKey.modal.unexpectedError"),
        });
      }
    }
  };

  const handleClose = () => {
    clearErrors("apiError");
    reset();
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={t("settings.apiKeys.addKey")}>
      <form
        onSubmit={(e) => {
          clearErrors();
          handleSubmit(onSubmit)(e);
        }}
      >
        {/* Email/Username Field */}
        {
          <div className="mt-4">
            <Subtitle>{t("apiKey.modal.name")}</Subtitle>
            <Controller
              name="name"
              control={control}
              rules={{ required: t("apiKey.modal.nameRequired") }}
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
        }

        {/* Role Field */}
        <div className="mt-4">
          <Subtitle>{t("apiKey.modal.role")}</Subtitle>
          <Controller
            name="role"
            control={control}
            rules={{ required: t("apiKey.modal.roleRequired") }}
            render={({ field }) => (
              <Select
                {...field}
                onChange={(selectedOption) =>
                  field.onChange(selectedOption?.name)
                }
                value={roles.find((role) => role.id === field.value)}
                options={roles}
                getOptionLabel={(role) => role.name}
                formatOptionLabel={(option) => (
                  <div className="flex items-center">
                    {option.name}
                    {option.description && (
                      <Icon
                        icon={InfoCircledIcon}
                        className="role-tooltip"
                        tooltip={option.description}
                        color="gray"
                        size="xs"
                      />
                    )}
                  </div>
                )}
                getOptionValue={(role) => role.id}
                placeholder={t("apiKey.modal.selectRole")}
              />
            )}
          />
          {errors.role && (
            <div className="text-sm text-rose-500 mt-1">
              {errors.role.message?.toString()}
            </div>
          )}
        </div>

        {/* Display API Error */}
        {errors.apiError && typeof errors.apiError.message === "string" && (
          <div className="text-red-500 mt-2">{errors.apiError.message}</div>
        )}

        {/* Submit and Cancel Buttons */}
        <div className="mt-6 flex gap-2">
          <Button color="orange" type="submit">
            {t("apiKey.modal.createApiKey")}
          </Button>
          <Button
            onClick={handleClose}
            variant="secondary"
            className="border border-orange-500 text-orange-500"
          >
            {t("common.actions.cancel")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
