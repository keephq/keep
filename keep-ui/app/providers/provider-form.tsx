// @ts-nocheck
import React, { useState } from "react";
import { useSession } from "../../utils/customAuth";
import { Provider } from "./providers";
import { getApiURL } from "../../utils/apiUrl";
import Image from "next/image";
import "./provider-form.css";
import { Title, Text, Button, Callout, Icon, Subtitle } from "@tremor/react";
import { ExclamationCircleIcon } from "@heroicons/react/20/solid";
import {
  QuestionMarkCircleIcon,
  ArrowLongRightIcon,
  ArrowLongLeftIcon,
} from "@heroicons/react/24/outline";
import { installWebhook } from "../../utils/helpers";
import { ProviderSemiAutomated } from "./provider-semi-automated";

type ProviderFormProps = {
  provider: Provider;
  formData: Record<string, string>; // New prop for form data
  formErrorsData: Record<string, string>; // New prop for form data
  onFormChange?: (
    formValues: Record<string, string>,
    formErrors: Record<string, string>
  ) => void;
  onConnectChange?: (isConnecting: boolean, isConnected: boolean) => void;
  closeModal: () => void;
  onAddProvider?: (provider: Provider) => void;
  isProviderNameDisabled?: boolean;
};

const ProviderForm = ({
  provider,
  formData,
  formErrorsData,
  onFormChange,
  onConnectChange,
  onAddProvider,
  closeModal,
  isProviderNameDisabled,
}: ProviderFormProps) => {
  console.log("Loading the ProviderForm component");
  const [formValues, setFormValues] = useState<{
    [key: string]: string | boolean;
  }>({
    provider_id: provider.id, // Include the provider ID in formValues
    ...formData,
    install_webhook: provider.can_setup_webhook,
  });
  const [formErrors, setFormErrors] = useState<{
    [key: string]: string;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const { data: session, status, update } = useSession();

  const [hoveredLabel, setHoveredLabel] = useState(null);

  const accessToken = session?.accessToken;

  const validateForm = (updatedFormValues) => {
    const errors = {};
    for (const [configKey, method] of Object.entries(provider.config)) {
      if (!formValues[configKey] && method.required) {
        errors[configKey] = true;
      }
      if (
        "validation" in method &&
        formValues[configKey] &&
        !method.validation(updatedFormValues[configKey])
      ) {
        errors[configKey] = true;
      }
      if (!formValues.provider_name) {
        errors["provider_name"] = true;
      }
    }
    markErrors(errors);
    return errors;
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setFormValues((prevValues) => ({ ...prevValues, [name]: value }));
    const updatedFormValues = { ...formValues, [name]: value };
    validateForm(updatedFormValues);
    onFormChange(updatedFormValues, formErrors);
  };

  const handleWebhookChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const checked = event.target.checked;
    setFormValues((prevValues) => ({
      ...prevValues,
      install_webhook: checked,
    }));
  };

  const markErrors = (errors: Record<string, boolean>) => {
    const inputElements = document.querySelectorAll(".form-group input");
    inputElements.forEach((input) => {
      const name = input.getAttribute("name");
      // @ts-ignore
      if (errors[name]) {
        input.classList.add("error");
      } else {
        input.classList.remove("error");
      }
    });
  };

  const validate = () => {
    const errors = validateForm(formValues);
    if (Object.keys(errors).length === 0) {
      markErrors(errors);
      return true;
    } else {
      setFormErrors(errors);
      markErrors(errors);
      return false;
    }
  };

  const submit = (requestUrl: string): Promise<any> => {
    return fetch(requestUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(formValues),
    })
      .then((response) => {
        if (!response.ok) {
          // If the response is not okay, throw the error message
          return response.json().then((errorData) => {
            throw new Error(
              `Error: ${response.status}, ${JSON.stringify(errorData)}`
            );
          });
        }
        const response_json = response.json();
        return response_json;
      })
      .then((data) => {
        setFormErrors({});
        return data;
      })
      .catch((error) => {
        console.error("Error:", error);
        throw error;
      });
  };

  const handleConnectClick = () => {
    if (!validate()) {
      return;
    }
    setIsLoading(true);
    onConnectChange(true, false);
    submit(`${getApiURL()}/providers/install`)
      .then((data) => {
        console.log("Connect Result:", data);
        setIsLoading(false);
        onConnectChange(false, true);
        if (formValues.install_webhook && provider.can_setup_webhook) {
          installWebhook(data as Provider, accessToken);
        }
        onAddProvider(data as Provider);
      })
      .catch((error) => {
        console.error("Connect failed:", error);
        const updatedFormErrors = { error: error.toString() };
        setFormErrors(updatedFormErrors);
        onFormChange(formValues, updatedFormErrors);
        setIsLoading(false);
        onConnectChange(false, false);
      });
  };

  console.log("ProviderForm component loaded");
  return (
    <div className="flex flex-col h-screen justify-between p-7">
      <div>
        <Title>
          Connect to{" "}
          {provider.type.charAt(0).toLocaleUpperCase() + provider.type.slice(1)}
        </Title>
        {provider.provider_description && (
          <Subtitle>{provider.provider_description}</Subtitle>
        )}
        <div className="flex items-center">
          <Image
            src={`/keep.png`}
            width={55}
            height={64}
            alt={provider.type}
            className="mt-5 mb-9 mr-2.5"
          />
          <div className="flex flex-col">
            <Icon
              icon={ArrowLongLeftIcon}
              size="xl"
              color="orange"
              className="py-0"
            />
            <Icon
              icon={ArrowLongRightIcon}
              size="xl"
              color="orange"
              className="py-0 pb-2.5"
            />
          </div>
          <Image
            src={`/icons/${provider.type}-icon.png`}
            width={64}
            height={55}
            alt={provider.type}
            className="mt-5 mb-9 ml-2.5"
          />
        </div>
        <form>
          <div className="form-group">
            <label htmlFor="provider_name" className="label-container mb-1">
              <Text>Provider Name</Text>
            </label>
            <input
              type="text"
              id="provider_name"
              name="provider_name"
              value={formValues.provider_name || ""}
              onChange={handleInputChange}
              placeholder="Enter provider name"
              color="orange"
              autoComplete="off"
              disabled={isProviderNameDisabled}
              className={
                isProviderNameDisabled
                  ? "disabled-input text-slate-400 bg-slate-100"
                  : ""
              }
              title={
                isProviderNameDisabled
                  ? "This field is disabled because it is pre-filled from the workflow."
                  : ""
              }
            />
          </div>
          {Object.keys(provider.config).map((configKey) => {
            const method = provider.config[configKey];
            const isHovered = hoveredLabel === configKey;
            return (
              <div className="form-group" key={configKey}>
                <label htmlFor={configKey} className="label-container mb-1">
                  <Text className="capitalize">
                    {method.description}
                    {method.required !== false ? "" : " (optional)"}
                  </Text>
                  {method.hint && (
                    <Icon
                      icon={QuestionMarkCircleIcon}
                      variant="simple"
                      color="gray"
                      size="sm"
                      tooltip={`${method.hint}`}
                    />
                  )}
                </label>
                <input
                  type={method.type}
                  id={configKey}
                  name={configKey}
                  value={formValues[configKey] || ""}
                  onChange={handleInputChange}
                  autoComplete="off"
                  placeholder={method.placeholder || "Enter " + configKey}
                />
              </div>
            );
          })}
          {provider.can_setup_webhook && (
            <div className="flex items-center w-full" key="install_webhook">
              <input
                type="checkbox"
                id="install_webhook"
                name="install_webhook"
                className="mr-2.5"
                onChange={handleWebhookChange}
                checked={formValues["install_webhook"] || false}
              />
              <label
                htmlFor="install_webhook"
                className="label-container w-full"
              >
                <Text className="capitalize">Install Webhook</Text>
                <Icon
                  icon={QuestionMarkCircleIcon}
                  variant="simple"
                  color="gray"
                  size="sm"
                  tooltip={`Whether to install Keep as a webhook integration in ${provider.type}.

                  This allows Keep to asynchronously receive alerts from ${provider.type}.
                  Please note that this will install a new integration in ${provider.type} and slightly modify your monitors/notificaiton policy to include Keep.`}
                />
              </label>
            </div>
          )}
          {provider.supports_webhook && (
            <ProviderSemiAutomated
              provider={provider}
              accessToken={accessToken}
            />
          )}
          {/* Hidden input for provider ID */}
          <input type="hidden" name="providerId" value={provider.id} />
        </form>
      </div>
      <div>
        {formErrors && (
          <Callout
            title="Connection Problem"
            icon={ExclamationCircleIcon}
            color="rose"
          >
            {JSON.stringify(formErrors, null, 2)}
          </Callout>
        )}
      </div>
      <div className="flex justify-end">
        <Button
          variant="secondary"
          color="orange"
          onClick={closeModal}
          className="mr-2.5"
          disabled={isLoading}
        >
          Cancel
        </Button>
        <Button loading={isLoading} onClick={handleConnectClick} color="orange">
          Connect
        </Button>
      </div>
    </div>
  );
};

export default ProviderForm;
