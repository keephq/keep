// TODO: refactor this file and separate in to smaller components
//  There's also a lot of s**t in here, but it works for now 🤷‍♂️
// @ts-nocheck
import React, { useEffect, useState, useRef, useCallback } from "react";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { Provider } from "./providers";
import { useApiUrl } from "utils/hooks/useConfig";
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
  Select,
  SelectItem,
  Card,
  Tab,
  TabList,
  TabGroup,
  TabPanel,
  TabPanels,
  Accordion,
  AccordionHeader,
  AccordionBody,
  Badge,
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
  PlusIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import { installWebhook } from "../../../utils/helpers";
import { ProviderSemiAutomated } from "./provider-semi-automated";
import ProviderFormScopes from "./provider-form-scopes";
import Link from "next/link";
import cookieCutter from "@boiseitguru/cookie-cutter";
import { useSearchParams } from "next/navigation";
import "./provider-form.css";
import { useProviders } from "@/utils/hooks/useProviders";
import TimeAgo from "react-timeago";
import { toast } from "react-toastify";

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
  isProviderNameDisabled?: boolean;
  installedProvidersMode: boolean;
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

const DictInput = ({ name, value, onChange, error }) => {
  const handleEntryChange = (index, field, newValue) => {
    const newEntries = value.map((entry, i) =>
      i === index ? { ...entry, [field]: newValue } : entry
    );
    onChange(newEntries);
  };

  const removeEntry = (index) => {
    const newEntries = value.filter((_, i) => i !== index);
    onChange(newEntries);
  };

  return (
    <div>
      {value.map((entry, index) => (
        <div key={index} className="flex items-center mb-2">
          <TextInput
            value={entry.key}
            onChange={(e) => handleEntryChange(index, "key", e.target.value)}
            placeholder="Key"
            className="mr-2"
          />
          <TextInput
            value={entry.value}
            onChange={(e) => handleEntryChange(index, "value", e.target.value)}
            placeholder="Value"
            className="mr-2"
          />
          <Button
            icon={TrashIcon}
            variant="secondary"
            color="orange"
            size="xs"
            onClick={() => removeEntry(index)}
          />
        </div>
      ))}
    </div>
  );
};

const ProviderForm = ({
  provider,
  formData,
  onFormChange,
  onConnectChange,
  closeModal,
  isProviderNameDisabled,
  installedProvidersMode,
  isLocalhost,
}: ProviderFormProps) => {
  console.log("Loading the ProviderForm component");
  const { mutate } = useProviders();
  const searchParams = useSearchParams();
  const [activeTabsState, setActiveTabsState] = useState({});
  const initialData = {
    provider_id: provider.id, // Include the provider ID in formValues
    ...formData,
  };
  if (provider.can_setup_webhook) {
    initialData["install_webhook"] = provider.can_setup_webhook;
    if (provider.pulling_enabled) {
      initialData["pulling_enabled"] = true;
    }
  }
  const [formValues, setFormValues] = useState<{
    [key: string]: string | boolean;
  }>(() => {
    const initialValues = {
      provider_id: provider.id,
      ...formData,
    };

    // Set default values for select inputs
    Object.entries(provider.config).forEach(([configKey, method]) => {
      if (
        method.type === "select" &&
        method.default &&
        !initialValues[configKey]
      ) {
        initialValues[configKey] = method.default;
      }
    });

    if (provider.can_setup_webhook) {
      initialValues["install_webhook"] = provider.can_setup_webhook;
      if (provider.pulling_enabled) {
        initialValues["pulling_enabled"] = provider.pulling_enabled;
      }
    }
    return initialValues;
  });

  const [formErrors, setFormErrors] = useState<string>(null);
  const [inputErrors, setInputErrors] = useState<{ [key: string]: boolean }>(
    {}
  );
  // Related to scopes
  const [providerValidatedScopes, setProviderValidatedScopes] = useState<{
    [key: string]: boolean | string;
  }>(provider.validatedScopes);
  const [triggerRevalidateScope, setTriggerRevalidateScope] = useState(0);
  const [refreshLoading, setRefreshLoading] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const inputFileRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);

  const api = useApi();

  const callInstallWebhook = async (e: Event) => {
    e.preventDefault();
    await installWebhook(provider, accessToken!, apiUrl);
  };

  async function handleOauth(e: MouseEvent) {
    e.preventDefault();
    const verifier = generateRandomString();
    cookieCutter.set("verifier", verifier);
    cookieCutter.set("oauth2_install_webhook", formValues.install_webhook);
    cookieCutter.set("oauth2_pulling_enabled", formValues.pulling_enabled);
    const verifierChallenge = base64urlencode(await sha256(verifier));

    let oauth2Url = provider.oauth2_url;
    if (searchParams?.get("domain")) {
      // TODO: this is a hack for Datadog OAuth2 since it can be initiated from different domains
      oauth2Url = oauth2Url?.replace(
        "datadoghq.com",
        searchParams.get("domain")
      );
    }

    let url = `${oauth2Url}&redirect_uri=${window.location.origin}/providers/oauth2/${provider.type}&code_challenge=${verifierChallenge}&code_challenge_method=S256`;

    if (provider.type === "slack") {
      url += `&state=${verifier}`;
    }

    window.location.assign(url);
  }

  useEffect(() => {
    // Set initial active tabs for each main group
    const initialActiveTabsState = {};
    Object.keys(groupedConfigs).forEach((mainGroup) => {
      const subGroups = getSubGroups(groupedConfigs[mainGroup]);
      if (subGroups.length > 0) {
        initialActiveTabsState[mainGroup] = subGroups[0];
      }
    });
    setActiveTabsState(initialActiveTabsState);
  }, []);

  useEffect(() => {
    if (triggerRevalidateScope !== 0) {
      setRefreshLoading(true);
      api
        .post(`/providers/${provider.id}/scopes`)
        .then((newValidatedScopes) => {
          setProviderValidatedScopes(newValidatedScopes);
          provider.validatedScopes = newValidatedScopes;
          mutate();
          setRefreshLoading(false);
        })
        .catch(() => {
          toast.error(
            "Failed to revalidate scopes, contact us if this persists"
          );
          setRefreshLoading(false);
        });
    }
  }, [triggerRevalidateScope, accessToken, provider.id]);

  async function deleteProvider() {
    if (confirm("Are you sure you want to delete this provider?")) {
      const response = await api
        .delete(`/providers/${provider.type}/${provider.id}`)
        .then(() => {
          mutate();
          closeModal();
        })
        .catch(() => {
          toast.error(`Failed to delete ${provider.type} 😢`);
        });
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

    setFormValues((prevValues) => {
      const updatedValues = { ...prevValues, [name]: value };
      onFormChange(updatedValues, formErrors);
      return updatedValues;
    });

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

  const handlePullingEnabledChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const checked = event.target.checked;
    setFormValues((prevValues) => ({
      ...prevValues,
      pulling_enabled: checked,
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

    return api
      .fetch(requestUrl, {
        method: method,
        headers: headers,
        body: body,
      })
      .then((jsonResponse) => jsonResponse)
      .catch((error) => {
        if (error instanceof KeepApiError) {
          const errorData = error.responseJson;
          // If the response is not okay, throw the error message
          if (response.status === 400) {
            throw `${errorData.detail}`;
          }
          if (response.status === 409) {
            throw `Provider with name ${formValues.provider_name} already exists`;
          }
          const errorDetail = errorData.detail;
          if (response.status === 412) {
            setProviderValidatedScopes(errorDetail);
          }
          throw `${provider.type} scopes are invalid: ${JSON.stringify(
            errorDetail,
            null,
            4
          )}`;
        }
      })
      .then((data) => {
        setFormErrors("");
        return data;
      });
  };

  const handleUpdateClick = (e: any) => {
    if (provider.webhook_required) callInstallWebhook(e);
    e.preventDefault();
    if (validate()) {
      setIsLoading(true);
      submit(`${apiUrl}/providers/${provider.id}`, "PUT")
        .then((data) => {
          setIsLoading(false);
          toast.success("Updated provider successfully", {
            position: "top-left",
          });
          mutate();
        })
        .catch((error) => {
          toast.error("Failed to update provider", { position: "top-left" });
          const updatedFormErrors = error.toString();
          setFormErrors(updatedFormErrors);
          onFormChange(formValues, updatedFormErrors);
          setIsLoading(false);
        });
    }
  };

  const handleConnectClick = async () => {
    if (validate()) {
      setIsLoading(true);
      onConnectChange(true, false);
      submit(`${apiUrl}/providers/install`)
        .then(async (data) => {
          console.log("Connect Result:", data);
          setIsLoading(false);
          onConnectChange(false, true);
          if (
            formValues.install_webhook &&
            provider.can_setup_webhook &&
            !isLocalhost
          ) {
            // mutate after webhook installation
            await installWebhook(data as Provider, accessToken, apiUrl);
          }
          mutate();
        })
        .catch((error) => {
          const updatedFormErrors = error.toString();

          if (updatedFormErrors.includes("SyntaxError")) {
            setFormErrors(
              "Bad response from API: Check the backend logs for more details"
            );
          } else if (updatedFormErrors.includes("Failed to fetch")) {
            setFormErrors(
              "Failed to connect to API: Check provider settings and your internet connection"
            );
          } else {
            setFormErrors(updatedFormErrors);
          }
          onFormChange(formValues, updatedFormErrors);
          setIsLoading(false);
          onConnectChange(false, false);
        });
    }
  };

  const installOrUpdateWebhookEnabled = provider.scopes
    ?.filter((scope) => scope.mandatory_for_webhook)
    .every((scope) => providerValidatedScopes[scope.name] === true);

  const addEntry = (fieldName) => (e) => {
    e.preventDefault();
    setFormValues((prevValues) => {
      const currentEntries = prevValues[fieldName] || [];
      const updatedEntries = [...currentEntries, { key: "", value: "" }];
      const updatedValues = { ...prevValues, [fieldName]: updatedEntries };
      onFormChange(updatedValues, formErrors);
      return updatedValues;
    });
  };

  const handleDictInputChange = (fieldName, newValue) => {
    setFormValues((prevValues) => {
      const updatedValues = { ...prevValues, [fieldName]: newValue };
      onFormChange(updatedValues, formErrors);
      return updatedValues;
    });
  };

  const renderFormField = (configKey, method) => {
    if (method.hidden) return null;

    const renderFieldHeader = () => (
      <label htmlFor={configKey} className="flex items-center mb-1">
        <Text className="capitalize">
          {method.description}
          {method.required === true && <span className="text-red-400">*</span>}
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
    );

    switch (method.type) {
      case "select":
        return (
          <>
            {renderFieldHeader()}
            <Select
              id={configKey}
              name={configKey}
              value={formValues[configKey] || method.default}
              onChange={(value) =>
                handleInputChange({ target: { name: configKey, value } })
              }
              placeholder={method.placeholder || `Select ${configKey}`}
              error={Object.keys(inputErrors).includes(configKey)}
              disabled={provider.provisioned}
            >
              {method.options.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </Select>
          </>
        );
      case "form":
        return (
          <div>
            <div className="flex items-center mb-2">
              {renderFieldHeader()}
              <Button
                className="ml-2"
                icon={PlusIcon}
                variant="secondary"
                color="orange"
                size="xs"
                onClick={addEntry(configKey)}
                disabled={provider.provisioned}
              >
                Add Entry
              </Button>
            </div>
            <DictInput
              name={configKey}
              value={formValues[configKey] || []}
              onChange={(value) => handleDictInputChange(configKey, value)}
              error={Object.keys(inputErrors).includes(configKey)}
              disabled={provider.provisioned}
            />
          </div>
        );
      case "file":
        return (
          <>
            {renderFieldHeader()}
            <Button
              color="orange"
              size="md"
              onClick={(e) => {
                e.preventDefault();
                inputFileRef.current.click();
              }}
              icon={ArrowDownOnSquareIcon}
              disabled={provider.provisioned}
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
              disabled={provider.provisioned}
            />
          </>
        );
      default:
        return (
          <>
            {renderFieldHeader()}
            <TextInput
              type={method.sensitive ? "password" : method.type}
              id={configKey}
              name={configKey}
              readOnly={method.readOnly}
              value={formValues[configKey] || ""}
              onChange={handleInputChange}
              autoComplete="off"
              error={Object.keys(inputErrors).includes(configKey)}
              placeholder={method.placeholder || `Enter ${configKey}`}
              disabled={provider.provisioned || method.readOnly}
            />
          </>
        );
    }
  };

  const requiredConfigs = Object.entries(provider.config)
    .filter(([_, config]) => config.required && !config.config_main_group)
    .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {});

  const optionalConfigs = Object.entries(provider.config)
    .filter(
      ([_, config]) =>
        !config.required && !config.hidden && !config.config_main_group
    )
    .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {});

  const groupConfigsByMainGroup = (configs) => {
    return Object.entries(configs).reduce((acc, [key, config]) => {
      const mainGroup = config.config_main_group;
      if (mainGroup) {
        if (!acc[mainGroup]) {
          acc[mainGroup] = {};
        }
        acc[mainGroup][key] = config;
      }
      return acc;
    }, {});
  };

  const groupConfigsBySubGroup = (configs) => {
    return Object.entries(configs).reduce((acc, [key, config]) => {
      const subGroup = config.config_sub_group || "default";
      if (!acc[subGroup]) {
        acc[subGroup] = {};
      }
      acc[subGroup][key] = config;
      return acc;
    }, {});
  };

  const getSubGroups = (configs) => {
    return [
      ...new Set(
        Object.values(configs).map((config) => config.config_sub_group)
      ),
    ].filter(Boolean);
  };

  const renderGroupFields = (groupName, groupConfigs) => {
    const subGroups = groupConfigsBySubGroup(groupConfigs);
    const subGroupNames = getSubGroups(groupConfigs);

    if (subGroupNames.length === 0) {
      // If no subgroups, render fields directly
      return (
        <Card className="mt-4">
          <Title>
            {groupName.charAt(0).toUpperCase() + groupName.slice(1)}
          </Title>
          {Object.entries(groupConfigs).map(([configKey, config]) => (
            <div className="mt-2.5" key={configKey}>
              {renderFormField(configKey, config)}
            </div>
          ))}
        </Card>
      );
    }

    return (
      <Card className="mt-4">
        <Title>{groupName.charAt(0).toUpperCase() + groupName.slice(1)}</Title>
        <TabGroup
          className="mt-2"
          onIndexChange={(index) =>
            setActiveTabsState((prev) => ({
              ...prev,
              [groupName]: subGroupNames[index],
            }))
          }
        >
          <TabList>
            {subGroupNames.map((subGroup) => (
              <Tab key={subGroup}>
                {subGroup.replace("_", " ").toUpperCase()}
              </Tab>
            ))}
          </TabList>
          <TabPanels>
            {subGroupNames.map((subGroup) => (
              <TabPanel key={subGroup}>
                {Object.entries(subGroups[subGroup] || {}).map(
                  ([configKey, config]) => (
                    <div className="mt-2.5" key={configKey}>
                      {renderFormField(configKey, config)}
                    </div>
                  )
                )}
              </TabPanel>
            ))}
          </TabPanels>
        </TabGroup>
      </Card>
    );
  };

  const groupedConfigs = groupConfigsByMainGroup(provider.config);
  console.log("ProviderForm component loaded");
  return (
    <div className="flex flex-col justify-between p-5">
      <div>
        <div className="flex flex-row">
          <Title>Connect to {provider.display_name}</Title>
          {/* Display the Provisioned Badge if the provider is provisioned */}
          {provider.provisioned && (
            <Badge color="orange" className="ml-2">
              Provisioned
            </Badge>
          )}

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
        {installedProvidersMode && provider.last_pull_time && (
          <Subtitle>
            Provider last pull time:{" "}
            <TimeAgo date={provider.last_pull_time + "Z"} />
          </Subtitle>
        )}
        {provider.provisioned && (
          <div className="w-full mt-4">
            <Callout
              icon={ExclamationTriangleIcon}
              color="orange"
              className="w-full"
            >
              <Text>
                Editing provisioned providers is not possible from UI.
              </Text>
            </Callout>
          </div>
        )}

        {provider.provider_description && (
          <Subtitle>{provider.provider_description}</Subtitle>
        )}
        {Object.keys(provider.config).length > 0 && (
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
        )}
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
            {Object.keys(provider.config).length > 0 && (
              <>
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
              </>
            )}
          </div>
          {/* Render required fields */}
          {Object.entries(requiredConfigs).map(([configKey, config]) => (
            <div className="mt-2.5" key={configKey}>
              {renderFormField(configKey, config)}
            </div>
          ))}

          {/* Render grouped fields */}
          {Object.entries(groupedConfigs).map(([groupName, groupConfigs]) => (
            <React.Fragment key={groupName}>
              {renderGroupFields(groupName, groupConfigs)}
            </React.Fragment>
          ))}

          {/* Render optional fields in a card */}
          {Object.keys(optionalConfigs).length > 0 && (
            <Accordion className="mt-4" defaultOpen={true}>
              <AccordionHeader>Provider Optional Settings</AccordionHeader>
              <AccordionBody>
                <Card>
                  {Object.entries(optionalConfigs).map(
                    ([configKey, config]) => (
                      <div className="mt-2.5" key={configKey}>
                        {renderFormField(configKey, config)}
                      </div>
                    )
                  )}
                </Card>
              </AccordionBody>
            </Accordion>
          )}
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
                    disabled={isLocalhost || provider.webhook_required}
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
                  {
                    // This is here because pulling is only enabled for providers we can get alerts from (e.g., support webhook)
                  }
                  <input
                    type="checkbox"
                    id="pulling_enabled"
                    name="pulling_enabled"
                    className="mr-2.5"
                    onChange={handlePullingEnabledChange}
                    checked={formValues["pulling_enabled"] || false}
                  />
                  <label
                    htmlFor="pulling_enabled"
                    className="flex items-center"
                  >
                    <Text className="capitalize">Pulling Enabled</Text>
                    <Icon
                      icon={QuestionMarkCircleIcon}
                      variant="simple"
                      color="gray"
                      size="sm"
                      tooltip={`Whether Keep should try to pull alerts automatically from the provider once in a while`}
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
            <>
              <div className="flex">
                <input
                  type="checkbox"
                  id="pulling_enabled"
                  name="pulling_enabled"
                  className="mr-2.5"
                  onChange={handlePullingEnabledChange}
                  checked={formValues["pulling_enabled"] || false}
                />
                <label htmlFor="pulling_enabled" className="flex items-center">
                  <Text className="capitalize">Pulling Enabled</Text>
                  <Icon
                    icon={QuestionMarkCircleIcon}
                    variant="simple"
                    color="gray"
                    size="sm"
                    tooltip={`Whether Keep should try to pull alerts automatically from the provider once in a while`}
                  />
                </label>
              </div>
              <Button
                icon={GlobeAltIcon}
                onClick={callInstallWebhook}
                variant="secondary"
                color="orange"
                className="mt-2.5"
                disabled={
                  !installOrUpdateWebhookEnabled || provider.provisioned
                }
                tooltip={
                  !installOrUpdateWebhookEnabled
                    ? "Fix required webhook scopes and refresh scopes to enable"
                    : "This uses server saved credentials. If needed, please use the `Update` button first"
                }
              >
                Install/Update Webhook
              </Button>
            </>
          )}
          {provider.supports_webhook && (
            <ProviderSemiAutomated provider={provider} />
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
        {installedProvidersMode && Object.keys(provider.config).length > 0 && (
          <>
            <Button
              onClick={deleteProvider}
              color="orange"
              className="mr-2.5"
              disabled={provider.provisioned}
              variant="secondary"
            >
              Delete
            </Button>
            <div className="relative">
              <Button
                loading={isLoading}
                onClick={handleUpdateClick}
                color="orange"
                disabled={provider.provisioned}
                variant="secondary"
              >
                Update
              </Button>
            </div>
          </>
        )}
        {!installedProvidersMode && Object.keys(provider.config).length > 0 && (
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
