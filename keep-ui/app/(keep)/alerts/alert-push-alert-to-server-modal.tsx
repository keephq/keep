import React, { useState, useEffect } from "react";
import { Button, Textarea, Subtitle, Callout } from "@tremor/react";
import {
  useForm,
  Controller,
  SubmitHandler,
  FieldValues,
} from "react-hook-form";
import Modal from "@/components/ui/Modal";
import { useProviders } from "utils/hooks/useProviders";
import { useAlerts } from "utils/hooks/useAlerts";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/api";
import { Select } from "@/shared/ui";

import { useRevalidateMultiple } from "@/shared/lib/state-utils";
import { DynamicImageProviderIcon } from "@/components/ui";

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

const PushAlertToServerModal = ({
  isOpen,
  handleClose,
  presetName,
}: PushAlertToServerModalProps) => {
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

  const { data: providersData } = useProviders();
  const providers = providersData?.providers || [];

  useEffect(() => {
    if (providers) {
      const sources = providers
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
  }, [providers]);

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
          message: error.message || "Failed to push alert",
        });
      } else {
        setError("apiError", {
          type: "manual",
          message: "An unexpected error occurred",
        });
      }
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Simulate Alert"
      className="w-[600px]"
    >
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="flex flex-col gap-2 mt-4"
      >
        <label className="block text-sm font-medium text-gray-700">
          Alert Source
        </label>
        <Controller
          name="source"
          control={control}
          rules={{ required: "Alert source is required" }}
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
                    className=""
                    // Add a key prop to force re-render when source changes
                    key={source.type}
                  />
                  <span className="ml-2">{source.name.toLowerCase()}</span>
                </div>
              )}
              getOptionValue={(source) => source.type}
              placeholder="Select alert source"
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
              title="About alert payload"
              color="orange"
              className="break-words mt-4"
            >
              Feel free to edit the payload as you want. However, some of the
              providers expects specific fields, so be careful.
            </Callout>

            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700">
                Alert Payload
              </label>
              <Controller
                name="alertJson"
                control={control}
                rules={{
                  required: "Alert payload is required",
                  validate: (value) => {
                    try {
                      JSON.parse(value);
                      return true;
                    } catch (e) {
                      return "Invalid JSON format";
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
            <Callout title="Error" color="rose">
              {errors.apiError.message?.toString()}
            </Callout>
          </div>
        )}

        <div className="mt-6 flex gap-2 justify-end">
          <Button
            onClick={handleClose}
            variant="secondary"
            className="border border-orange-500 text-orange-500"
          >
            Cancel
          </Button>
          <Button color="orange" type="submit">
            Submit
          </Button>
        </div>
      </form>
    </Modal>
  );
};

export default PushAlertToServerModal;
