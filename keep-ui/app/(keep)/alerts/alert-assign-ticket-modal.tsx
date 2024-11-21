import React from "react";
import Select, { components } from "react-select";
import { Button, TextInput, Text } from "@tremor/react";
import { PlusIcon } from "@heroicons/react/20/solid";
import { useForm, Controller, SubmitHandler } from "react-hook-form";
import { Providers } from "../providers/providers";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useApiUrl } from "utils/hooks/useConfig";
import { AlertDto } from "./models";
import Modal from "@/components/ui/Modal";

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

const AlertAssignTicketModal = ({
  handleClose,
  ticketingProviders,
  alert,
}: AlertAssignTicketModalProps) => {
  const {
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<FormData>();
  // get the token
  const { data: session } = useSession();
  const apiUrl = useApiUrl();

  // if this modal should not be open, do nothing
  if (!alert) return null;

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

      const response = await fetch(`${apiUrl}/alerts/enrich`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify(requestData),
      });

      if (response.ok) {
        // Handle success
        console.log("Ticket assigned successfully");
        alert.ticket_url = data.ticket_url;
        handleClose();
      } else {
        // Handle error
        console.error("Failed to assign ticket");
      }
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
      label: "Add another ticketing provider",
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
              <img
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
              <img
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
      onClose={handleClose}
      title="Assign Ticket"
      className="w-[400px]"
    >
      <div className="relative bg-white p-6 rounded-lg">
        {ticketingProviders.length > 0 ? (
          <form onSubmit={handleSubmit(onSubmit)} className="mt-4">
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700">
                Ticket Provider
              </label>
              <Controller
                name="provider"
                control={control}
                rules={{ required: "Provider is required" }}
                render={({ field }) => (
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
                Ticket URL
              </label>
              <Controller
                name="ticket_url"
                control={control}
                rules={{
                  required: "URL is required",
                  pattern: {
                    value: /^(https?|http):\/\/[^\s/$.?#].[^\s]*$/i,
                    message: "Invalid URL format",
                  },
                }}
                render={({ field }) => (
                  <>
                    <TextInput
                      {...field}
                      className="w-full mt-1"
                      placeholder="Ticket URL"
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
            <div className="mt-6 flex gap-2">
              <Button color="orange" type="submit">
                <Text>Assign Ticket</Text>
              </Button>
              <Button
                onClick={handleClose}
                variant="secondary"
                className="border border-orange-500 text-orange-500"
              >
                <Text>Cancel</Text>
              </Button>
            </div>
          </form>
        ) : (
          <div className="text-center mt-4">
            <Text className="text-gray-700 text-sm">
              Please connect at least one ticketing provider to use this
              feature.
            </Text>
            <Button
              onClick={() =>
                window.open("/providers?labels=ticketing", "_blank")
              }
              color="orange"
              className="mt-4 mr-4"
            >
              <Text>Connect Ticketing Provider</Text>
            </Button>
            <Button
              onClick={handleClose}
              color="orange"
              variant="secondary"
              className="mt-4 border border-orange-500 text-orange-500"
            >
              Close
            </Button>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default AlertAssignTicketModal;
