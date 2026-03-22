import React from "react";
import Select, { components } from "react-select";
import { Button, TextInput, Text, Icon } from "@tremor/react";
import { PlusIcon } from "@heroicons/react/20/solid";
import { useForm, Controller, SubmitHandler } from "react-hook-form";
import { Providers } from "@/shared/api/providers";
import { AlertDto } from "@/entities/alerts/model";
import Modal from "@/components/ui/Modal";
import { useApi } from "@/shared/lib/hooks/useApi";
import { QuestionMarkCircleIcon } from "@heroicons/react/24/outline";
import { DynamicImageProviderIcon } from "@/components/ui";
import { useI18n } from "@/i18n/hooks/useI18n";

interface AlertAssignTicketModalProps {
  handleClose: () => void;
  ticketingProviders: Providers;
  alert: AlertDto | null;
}

interface OptionType {
  value: string;
  label: string;
  id: string;
  type: string;
  icon?: string;
  isAddProvider?: boolean;
}

interface FormData {
  provider: {
    id: string;
    value: string;
    type: string;
  };
  ticket_url: string;
}

export const AlertAssignTicketModal = ({
  handleClose,
  ticketingProviders,
  alert,
}: AlertAssignTicketModalProps) => {
  const { t } = useI18n();
  const api = useApi();
  const {
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormData>();

  // if this modal should not be open, do nothing
  if (!alert) return null;

  const handleModalClose = () => {
    reset();
    handleClose();
  };

  const onSubmit: SubmitHandler<FormData> = async (data) => {
    try {
      // build the formData
      const requestData = {
        enrichments: {
          ticket_type: data.provider.type,
          ticket_url: data.ticket_url,
          ticket_provider_id: data.provider.value,
        },
        fingerprint: alert.fingerprint,
      };
      const response = await api.post(`/alerts/enrich`, requestData);
      alert.ticket_url = data.ticket_url;
      handleModalClose();
    } catch (error) {
      // Handle unexpected error
      console.error("An unexpected error occurred");
    }
  };

  const providerOptions: OptionType[] = ticketingProviders.map((provider) => ({
    id: provider.id,
    value: provider.id,
    label: provider.details.name || "",
    type: provider.type,
  }));

  const customOptions: OptionType[] = [
    ...providerOptions,
    {
      value: "add_provider",
      label: t("alerts.assignTicket.addAnotherProvider"),
      icon: "plus",
      isAddProvider: true,
      id: "add_provider",
      type: "",
    },
  ];

  const handleOnChange = (option: any) => {
    if (option.value === "add_provider") {
      window.open("/providers?labels=ticketing", "_blank");
    }
  };

  const Option = (props: any) => {
    // Check if the option is 'add_provider'
    const isAddProvider = props.data.isAddProvider;

    return (
      <components.Option {...props}>
        <div className="flex items-center">
          {isAddProvider ? (
            <PlusIcon className="h-5 w-5 text-gray-400 mr-2" />
          ) : (
            props.data.type && (
              <DynamicImageProviderIcon
                src={`/icons/${props.data.type}-icon.png`}
                alt=""
                style={{ height: "20px", marginRight: "10px" }}
              />
            )
          )}
          <span style={{ color: isAddProvider ? "gray" : "inherit" }}>
            {props.data.label}
          </span>
        </div>
      </components.Option>
    );
  };

  const SingleValue = (props: any) => {
    const { children, data } = props;

    return (
      <components.SingleValue {...props}>
        <div className="flex items-center">
          {data.isAddProvider ? (
            <PlusIcon className="h-5 w-5 text-gray-400 mr-2" />
          ) : (
            data.type && (
              <DynamicImageProviderIcon
                src={`/icons/${data.type}-icon.png`}
                alt=""
                style={{ height: "20px", marginRight: "10px" }}
              />
            )
          )}
          {children}
        </div>
      </components.SingleValue>
    );
  };

  // if alert is not null, open the modal
  const isOpen = alert !== null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleModalClose}
      title={t("alerts.actions.assignTicket")}
      beforeTitle={alert?.name}
      className="w-[400px]"
    >
      <div className="relative bg-white rounded-lg">
        {ticketingProviders.length > 0 ? (
          <form onSubmit={handleSubmit(onSubmit)} className="mt-4">
            <div className="mt-4">
              <div className="flex flex-row items-center mb-2">
                <label className="block text-sm font-medium text-gray-700">
                  {t("alerts.assignTicket.ticketProvider")}
                </label>
                <Icon
                  icon={QuestionMarkCircleIcon}
                  tooltip={t("alerts.assignTicket.ticketProviderTooltip")}
                  className="w-2 h-2 ml-2 z-[60]"
                />
              </div>
              <Controller
                name="provider"
                control={control}
                rules={{ required: t("alerts.assignTicket.providerRequired") }}
                render={({ field }) => (
                  // FIX: Select prevent modal from closing on Escape key
                  <Select
                    {...field}
                    options={customOptions}
                    onChange={(option) => {
                      field.onChange(option);
                      handleOnChange(option);
                    }}
                    components={{ Option, SingleValue }}
                  />
                )}
              />
            </div>
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700">
                {t("alerts.assignTicket.ticketUrl")}
              </label>
              <Controller
                name="ticket_url"
                control={control}
                rules={{
                  required: t("alerts.assignTicket.urlRequired"),
                  pattern: {
                    value: /^(https?|http):\/\/[^\s/$.?#].[^\s]*$/i,
                    message: t("alerts.assignTicket.urlInvalid"),
                  },
                }}
                render={({ field }) => (
                  <>
                    <TextInput
                      {...field}
                      className="w-full mt-1"
                      placeholder={t("alerts.assignTicket.ticketUrlPlaceholder")}
                    />
                    {errors.ticket_url && (
                      <span className="text-red-500">
                        {errors.ticket_url.message}
                      </span>
                    )}
                  </>
                )}
              />
            </div>
            <div className="mt-6 flex gap-2 justify-end">
              <Button
                onClick={handleModalClose}
                variant="secondary"
                color="orange"
              >
                {t("common.actions.cancel")}
              </Button>
              <Button
                color="orange"
                variant="primary"
                type="submit"
                disabled={isSubmitting}
              >
                {t("alerts.actions.assignTicket")}
              </Button>
            </div>
          </form>
        ) : (
          <div className="text-center mt-4">
            <Text className="text-gray-700 text-sm">
              {t("alerts.assignTicket.noProviderMessage")}
            </Text>
            <Button
              onClick={() =>
                window.open("/providers?labels=ticketing", "_blank")
              }
              color="orange"
              className="mt-4 mr-4"
            >
              <Text>{t("alerts.assignTicket.connectProvider")}</Text>
            </Button>
            <Button
              onClick={handleModalClose}
              color="orange"
              variant="secondary"
              className="mt-4 border border-orange-500 text-orange-500"
            >
              {t("common.actions.close")}
            </Button>
          </div>
        )}
      </div>
    </Modal>
  );
};
