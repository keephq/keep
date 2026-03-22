import React, { useState, useEffect } from "react";
import { Button, Textarea, Callout } from "@tremor/react";
import {
  useForm,
  Controller,
  SubmitHandler,
  FieldValues,
} from "react-hook-form";
import Modal from "@/components/ui/Modal";
import { useProviders } from "@/utils/hooks/useProviders";
import { useAlerts } from "@/entities/alerts/model/useAlerts";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/api";
import { Select } from "@/shared/ui";

import { useRevalidateMultiple } from "@/shared/lib/state-utils";
import { DynamicImageProviderIcon } from "@/components/ui";
import { useI18n } from "@/i18n/hooks/useI18n";

interface PushAlertToServerModalProps {
  isOpen: boolean;
  handleClose: () => void;
  presetName: string;
}

interface AlertSource {
  name: string;
  type: string;
  alertExample: string;
}

export const PushAlertToServerModal = ({
  isOpen,
  handleClose,
  presetName,
}: PushAlertToServerModalProps) => {
  const { t } = useI18n();
  const [alertSources, setAlertSources] = useState<AlertSource[]>([]);
  const revalidateMultiple = useRevalidateMultiple();
  const presetsMutator = () => revalidateMultiple(["/preset"]);
  const { alertsMutator: mutateAlerts } = useAlerts();

  const {
    control,
    handleSubmit,
    setValue,
    setError,
    clearErrors,
    watch,
    formState: { errors },
  } = useForm();

  const selectedSource = watch("source");
  const api = useApi();

  const { data: providersData } = useProviders({ revalidateOnFocus: false });

  useEffect(() => {
    if (providersData?.providers) {
      const sources = providersData.providers
        .filter((provider) => provider.alertExample)
        .map((provider) => {
          return {
            name: provider.display_name,
            type: provider.type,
            alertExample: JSON.stringify(provider.alertExample, null, 2),
          };
        });
      setAlertSources(sources);
    }
  }, [providersData]);

  const handleSourceChange = (source: AlertSource | null) => {
    if (source) {
      setValue("source", source);
      setValue("alertJson", source.alertExample);
      clearErrors("source");
    }
  };

  const onSubmit: SubmitHandler<FieldValues> = async (data) => {
    try {
      // if type is string, parse it to JSON
      if (typeof data.alertJson === "string") {
        data.alertJson = JSON.parse(data.alertJson);
      }

      const response = await api.post(
        `/alerts/event/${data.source.type}`,
        data.alertJson
      );

      mutateAlerts();
      presetsMutator();
      handleClose();
    } catch (error) {
      if (error instanceof KeepApiError) {
        setError("apiError", {
          type: "manual",
          message: error.message || t("alerts.simulate.failedToPush"),
        });
      } else {
        setError("apiError", {
          type: "manual",
          message: t("errors.generic"),
        });
      }
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={t("alerts.simulate.title")}
      className="w-[600px]"
    >
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="flex flex-col gap-2 mt-4"
      >
        <label className="block text-sm font-medium text-gray-700">
          {t("alerts.simulate.alertSource")}
        </label>
        <Controller
          name="source"
          control={control}
          rules={{ required: t("alerts.simulate.alertSourceRequired") }}
          render={({ field: { value, onChange, ...field } }) => (
            // FIX: Select prevent modal from closing on Escape key
            <Select
              {...field}
              value={value}
              onChange={handleSourceChange}
              options={alertSources}
              getOptionLabel={(source) => source.name}
              formatOptionLabel={(source) => (
                <div className="flex items-center" key={source.type}>
                  <DynamicImageProviderIcon
                    src={`/icons/${source.type}-icon.png`}
                    width={32}
                    height={32}
                    alt={source.type}
                    providerType={source.type}
                    className=""
                    // Add a key prop to force re-render when source changes
                    key={source.type}
                  />
                  <span className="ml-2">{source.name.toLowerCase()}</span>
                </div>
              )}
              getOptionValue={(source) => source.type}
              placeholder={t("alerts.simulate.selectAlertSource")}
            />
          )}
        />
        {errors.source && (
          <div className="text-sm text-rose-500 mt-1">
            {errors.source.message?.toString()}
          </div>
        )}

        {selectedSource && (
          <>
            <Callout
              title={t("alerts.simulate.aboutPayloadTitle")}
              color="orange"
              className="break-words mt-4"
            >
              {t("alerts.simulate.aboutPayloadDescription")}
            </Callout>

            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700">
                {t("alerts.simulate.alertPayload")}
              </label>
              <Controller
                name="alertJson"
                control={control}
                rules={{
                  required: t("alerts.simulate.alertPayloadRequired"),
                  validate: (value) => {
                    try {
                      JSON.parse(value);
                      return true;
                    } catch (e) {
                      return t("alerts.simulate.invalidJson");
                    }
                  },
                }}
                render={({ field }) => (
                  <Textarea {...field} rows={20} className="w-full mt-1" />
                )}
              />
              {errors.alertJson && (
                <div className="text-sm text-rose-500 mt-1">
                  {errors.alertJson.message?.toString()}
                </div>
              )}
            </div>
          </>
        )}

        {errors.apiError && (
          <div className="text-sm text-rose-500 mt-4">
            <Callout title={t("common.messages.error")} color="rose">
              {errors.apiError.message?.toString()}
            </Callout>
          </div>
        )}

        <div className="mt-6 flex gap-2 justify-end">
          <Button color="orange" onClick={handleClose} variant="secondary">
            {t("common.actions.cancel")}
          </Button>
          <Button color="orange" variant="primary" type="submit">
            {t("common.actions.submit")}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
