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
import { useTranslations } from "next-intl";
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
  const t = useTranslations("settings.createApiKey");
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
          message: error.message || t("failedToCreateApiKey"),
        });
      } else {
        setError("apiError", {
          type: "manual",
          message: t("unexpectedError"),
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
    <Modal isOpen={isOpen} onClose={handleClose} title={t("createApiKey")}>
      <form
        onSubmit={(e) => {
          clearErrors();
          handleSubmit(onSubmit)(e);
        }}
      >
        {/* Email/Username Field */}
        {
          <div className="mt-4">
            <Subtitle>{t("name")}</Subtitle>
            <Controller
              name="name"
              control={control}
              rules={{ required: t("nameRequired") }}
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
          <Subtitle>{t("role")}</Subtitle>
          <Controller
            name="role"
            control={control}
            rules={{ required: t("roleRequired") }}
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
                placeholder={t("selectRole")}
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
            {t("createApiKey")}{" "}
          </Button>
          <Button
            onClick={handleClose}
            variant="secondary"
            className="border border-orange-500 text-orange-500"
          >
            {t("cancel")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
