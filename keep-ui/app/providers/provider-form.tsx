// TODO: refactor this file and separate in to smaller components
//  There's also a lot of s**t in here, but it works for now 🤷‍♂️
// @ts-nocheck
import React, { useEffect, useState, useRef } from "react";
import { useSession } from "next-auth/react";
import { Provider } from "./providers";
import { getApiURL } from "../../utils/apiUrl";
import Image from "next/image";
import {
  Title,
  Text,
  Button,
  Callout,
  Icon,
  Subtitle,
  Divider,
  TextInput,
} from "@tremor/react";
import {
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/20/solid";
import {
  QuestionMarkCircleIcon,
  ArrowLongRightIcon,
  ArrowLongLeftIcon,
  ArrowTopRightOnSquareIcon,
  ArrowDownOnSquareIcon,
  GlobeAltIcon,
  DocumentTextIcon,
} from "@heroicons/react/24/outline";
import { installWebhook } from "../../utils/helpers";
import { ProviderSemiAutomated } from "./provider-semi-automated";
import ProviderFormScopes from "./provider-form-scopes";
import Link from "next/link";
import cookieCutter from "@boiseitguru/cookie-cutter";

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
  installedProvidersMode: boolean;
  onDelete?: (provider: Provider) => void;
  isLocalhost?: boolean;
};

function dec2hex(dec) {
  return ("0" + dec.toString(16)).substr(-2);
}

function generateRandomString() {
  var array = new Uint32Array(56 / 2);
  window.crypto.getRandomValues(array);
  return Array.from(array, dec2hex).join("");
}

function sha256(plain) {
  // returns promise ArrayBuffer
  const encoder = new TextEncoder();
  const data = encoder.encode(plain);
  return window.crypto.subtle.digest("SHA-256", data);
}

function base64urlencode(a) {
  var str = "";
  var bytes = new Uint8Array(a);
  var len = bytes.byteLength;
  for (var i = 0; i < len; i++) {
    str += String.fromCharCode(bytes[i]);
  }
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

const ProviderForm = ({
  provider,
  formData,
  onFormChange,
  onConnectChange,
  onAddProvider,
  closeModal,
  isProviderNameDisabled,
  installedProvidersMode,
  onDelete,
  isLocalhost,
}: ProviderFormProps) => {
  console.log("Loading the ProviderForm component");
  const initialData = {
    provider_id: provider.id, // Include the provider ID in formValues
    ...formData,
  };
  if (provider.can_setup_webhook) {
    initialData["install_webhook"] = provider.can_setup_webhook;
  }
  const [formValues, setFormValues] = useState<{
    [key: string]: string | boolean;
  }>(initialData);
  const [formErrors, setFormErrors] = useState<string>(null);
  const [inputErrors, setInputErrors] = useState<{ [key: string]: boolean }>(
    {}
  );
  const [isModalOpen, setIsModalOpen] = useState(false);
  // Related to scopes
  const [providerValidatedScopes, setProviderValidatedScopes] = useState<{
    [key: string]: boolean | string;
  }>(provider.validatedScopes);
  const [triggerRevalidateScope, setTriggerRevalidateScope] = useState(0);
  const [refreshLoading, setRefreshLoading] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const inputFileRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);

  const { data: session } = useSession();

  const accessToken = session?.accessToken;

  const callInstallWebhook = async (e: Event) => {
    await installWebhook(provider, accessToken!);
    e.preventDefault();
  };

  async function handleOauth(e: MouseEvent) {
    e.preventDefault();
    const verifier = generateRandomString();
    cookieCutter.set("verifier", verifier);
    const verifierChallenge = base64urlencode(await sha256(verifier));
    window.location.assign(
      `${provider.oauth2_url}&redirect_uri=${window.location.origin}/providers/oauth2/${provider.type}&code_challenge=${verifierChallenge}&code_challenge_method=S256`
    );
  }

  useEffect(() => {
    if (triggerRevalidateScope !== 0) {
      setRefreshLoading(true);
      fetch(`${getApiURL()}/providers/${provider.id}/scopes`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      }).then((response) => {
        if (response.ok) {
          response.json().then((newValidatedScopes) => {
            setProviderValidatedScopes(newValidatedScopes);
            provider.validatedScopes = newValidatedScopes;
            onAddProvider(provider);
            setRefreshLoading(false);
          });
        } else {
          setRefreshLoading(false);
        }
      });
    }
  }, [triggerRevalidateScope, accessToken, provider.id]);

  async function deleteProvider() {
    if (confirm("Are you sure you want to delete this provider?")) {
      const response = await fetch(
        `${getApiURL()}/providers/${provider.type}/${provider.id}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${session?.accessToken!}`,
          },
        }
      );
      if (response.ok) {
        onDelete!(provider);
        closeModal();
      } else {
        toast.error(`Failed to delete ${provider.type} 😢`);
      }
    }
  }

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
    setInputErrors(errors);
    return errors;
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, type } = event.target;
    let value;

    // If the input is a file, retrieve the file object, otherwise retrieve the value
    if (type === "file") {
      value = event.target.files?.[0]; // Assumes single file upload
    } else {
      value = event.target.value;
    }

    setFormValues((prevValues) => ({ ...prevValues, [name]: value }));
    const updatedFormValues = { ...formValues, [name]: value };

    if (Object.keys(inputErrors).includes(name) && value !== "") {
      const updatedInputErrors = { ...inputErrors };
      delete updatedInputErrors[name];
      setInputErrors(updatedInputErrors);
    }

    onFormChange(updatedFormValues, formErrors);
  };

  const handleWebhookChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const checked = event.target.checked;
    setFormValues((prevValues) => ({
      ...prevValues,
      install_webhook: checked,
    }));
  };

  const validate = () => {
    const errors = validateForm(formValues);
    if (Object.keys(errors).length === 0) {
      return true;
    } else {
      setFormErrors(
        `Missing required fields: ${JSON.stringify(
          Object.keys(errors),
          null,
          4
        )}`
      );
      return false;
    }
  };

  const submit = (
    requestUrl: string,
    method: string = "POST"
  ): Promise<any> => {
    let headers = {
      Authorization: `Bearer ${accessToken}`,
    };

    let body;

    if (Object.values(formValues).some((value) => value instanceof File)) {
      // FormData for file uploads
      let formData = new FormData();
      for (let key in formValues) {
        formData.append(key, formValues[key]);
      }
      body = formData;
    } else {
      // Standard JSON for non-file submissions
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(formValues);
    }

    return fetch(requestUrl, {
      method: method,
      headers: headers,
      body: body,
    })
      .then((response) => {
        const response_json = response.json();
        if (!response.ok) {
          // If the response is not okay, throw the error message
          return response_json.then((errorData) => {
            const errorDetail = errorData.detail;
            if (response.status === 412) {
              setProviderValidatedScopes(errorDetail);
            }
            throw `Scopes are invalid for ${provider.type}: ${JSON.stringify(
              errorDetail,
              null,
              4
            )}`;
          });
        }
        return response_json;
      })
      .then((data) => {
        setFormErrors("");
        return data;
      });
  };

  const handleUpdateClick = (e: any) => {
    e.preventDefault();
    if (validate()) {
      setIsLoading(true);
      submit(`${getApiURL()}/providers/${provider.id}`, "PUT")
        .then((data) => {
          setIsLoading(false);
          onAddProvider({ ...provider, ...data } as Provider);
        })
        .catch((error) => {
          const updatedFormErrors = error.toString();
          setFormErrors(updatedFormErrors);
          onFormChange(formValues, updatedFormErrors);
          setIsLoading(false);
        });
    }
  };

  const handleConnectClick = () => {
    if (validate()) {
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
          onAddProvider({ ...provider, ...data } as Provider);
        })
        .catch((error) => {
          const updatedFormErrors = error.toString();
          setFormErrors(updatedFormErrors);
          onFormChange(formValues, updatedFormErrors);
          setIsLoading(false);
          onConnectChange(false, false);
        });
    }
  };

  const installOrUpdateWebhookEnabled = provider.scopes
    ?.filter((scope) => scope.mandatory_for_webhook)
    .every((scope) => providerValidatedScopes[scope.name] === true);

  console.log("ProviderForm component loaded");
  return (
    <div className="flex flex-col h-full justify-between p-5">
      <div>
        <div className="flex flex-row">
          <Title>Connect to {provider.display_name}</Title>
          <Link
            href={`http://docs.keephq.dev/providers/documentation/${provider.type}-provider`}
            target="_blank"
          >
            <Icon
              icon={DocumentTextIcon}
              variant="simple"
              color="gray"
              size="sm"
              tooltip={`${provider.type} provider documentation`}
            />
          </Link>
        </div>

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
        {provider.scopes?.length > 0 && (
          <ProviderFormScopes
            provider={provider}
            validatedScopes={providerValidatedScopes}
            installedProvidersMode={installedProvidersMode}
            triggerRevalidateScope={setTriggerRevalidateScope}
            refreshLoading={refreshLoading}
          />
        )}
        <form>
          <div className="form-group">
            {provider.oauth2_url && !provider.installed ? (
              <>
                <Button
                  color="orange"
                  variant="secondary"
                  icon={ArrowTopRightOnSquareIcon}
                  onClick={handleOauth}
                >
                  Install with OAuth2
                </Button>
                <Divider />
              </>
            ) : null}
            <label htmlFor="provider_name" className="label-container mb-1">
              <Text>
                Provider Name
                <span className="text-red-400">*</span>
              </Text>
            </label>
            <TextInput
              type="text"
              id="provider_name"
              name="provider_name"
              value={formValues.provider_name || ""}
              onChange={handleInputChange}
              placeholder="Enter provider name"
              color="orange"
              autoComplete="off"
              disabled={isProviderNameDisabled}
              error={Object.keys(inputErrors).includes("provider_name")}
              title={
                isProviderNameDisabled
                  ? "This field is disabled because it is pre-filled from the workflow."
                  : ""
              }
            />
          </div>
          {Object.keys(provider.config).map((configKey) => {
            const method = provider.config[configKey];
            if (method.hidden) return null;
            const isSensitive = method.sensitive;
            return (
              <div className="mt-2.5" key={configKey}>
                <label htmlFor={configKey} className="flex items-center mb-1">
                  <Text className="capitalize">
                    {method.description}
                    {method.required === true ? (
                      <span className="text-red-400">*</span>
                    ) : null}
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

                {method.type === "file" ? (
                  <>
                    <Button
                      color="orange"
                      size="md"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        inputFileRef.current.click(); // this line triggers the file input
                      }}
                      icon={ArrowDownOnSquareIcon}
                    >
                      {selectedFile
                        ? `File Chosen: ${selectedFile}`
                        : `Upload a ${method.name}`}
                    </Button>

                    <input
                      ref={inputFileRef}
                      type="file"
                      id={configKey}
                      name={configKey}
                      accept={method.file_type}
                      style={{ display: "none" }}
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          setSelectedFile(e.target.files[0].name);
                        }
                        handleInputChange(e);
                      }}
                    />
                  </>
                ) : (
                  <TextInput
                    type={isSensitive ? "password" : method.type} // Display as password if sensitive
                    id={configKey}
                    name={configKey}
                    value={formValues[configKey] || ""}
                    onChange={handleInputChange}
                    autoComplete="off"
                    error={Object.keys(inputErrors).includes(configKey)}
                    placeholder={method.placeholder || "Enter " + configKey}
                  />
                )}
              </div>
            );
          })}
          <div className="w-full mt-2" key="install_webhook">
            {provider.can_setup_webhook && !installedProvidersMode && (
              <div className={`${isLocalhost ? "bg-gray-100 p-2" : ""}`}>
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="install_webhook"
                    name="install_webhook"
                    className="mr-2.5"
                    onChange={handleWebhookChange}
                    checked={
                      (formValues["install_webhook"] || false) && !isLocalhost
                    }
                    disabled={isLocalhost}
                  />
                  <label
                    htmlFor="install_webhook"
                    className="flex items-center"
                  >
                    <Text className="capitalize">Install Webhook</Text>
                    <Icon
                      icon={QuestionMarkCircleIcon}
                      variant="simple"
                      color="gray"
                      size="sm"
                      tooltip={`Whether to install Keep as a webhook integration in ${provider.type}. This allows Keep to asynchronously receive alerts from ${provider.type}. Please note that this will install a new integration in ${provider.type} and slightly modify your monitors/notification policy to include Keep.`}
                    />
                  </label>
                </div>
                {isLocalhost && (
                  <span className="text-sm">
                    <Callout
                      className="mt-4"
                      icon={ExclamationTriangleIcon}
                      color="gray"
                    >
                      <a
                        href="https://docs.keephq.dev/development/external-url"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Webhook installation is disabled because Keep is running
                        without an external URL.
                        <br />
                        <br />
                        Click to learn more
                      </a>
                    </Callout>
                  </span>
                )}
              </div>
            )}
          </div>

          {provider.can_setup_webhook && installedProvidersMode && (
            <Button
              icon={GlobeAltIcon}
              onClick={callInstallWebhook}
              variant="secondary"
              color="orange"
              className="mt-2.5"
              disabled={!installOrUpdateWebhookEnabled}
              tooltip={
                !installOrUpdateWebhookEnabled
                  ? "Fix required webhook scopes and refresh scopes to enable"
                  : "This uses server saved credentials. If needed, please use the `Update` button first"
              }
            >
              Install/Update Webhook
            </Button>
          )}
          {provider.supports_webhook && (
            <ProviderSemiAutomated
              provider={provider}
              accessToken={accessToken}
            />
          )}
          {formErrors && (
            <Callout
              title="Connection Problem"
              icon={ExclamationCircleIcon}
              className="my-5"
              color="rose"
            >
              {formErrors}
            </Callout>
          )}
          {/* Hidden input for provider ID */}
          <input type="hidden" name="providerId" value={provider.id} />
        </form>
      </div>

      <div className="flex justify-end mt-5">
        <Button
          variant="secondary"
          color="orange"
          onClick={closeModal}
          className="mr-2.5"
          disabled={isLoading}
        >
          Cancel
        </Button>
        {installedProvidersMode && (
          <>
            <Button onClick={deleteProvider} color="red" className="mr-2.5">
              Delete
            </Button>
            <Button
              loading={isLoading}
              onClick={handleUpdateClick}
              color="orange"
            >
              Update
            </Button>
          </>
        )}
        {!installedProvidersMode && (
          <Button
            loading={isLoading}
            onClick={handleConnectClick}
            color="orange"
          >
            Connect
          </Button>
        )}
      </div>
    </div>
  );
};

export default ProviderForm;
