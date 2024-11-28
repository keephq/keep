import React, { useState, useRef, useMemo } from "react";
import { Provider, ProviderAuthConfig } from "./providers";
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
  Switch,
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
import { ProviderSemiAutomated } from "./provider-semi-automated";
import ProviderFormScopes from "./provider-form-scopes";
import Link from "next/link";
import cookieCutter from "@boiseitguru/cookie-cutter";
import { useSearchParams } from "next/navigation";
import "./provider-form.css";
import { toast } from "react-toastify";
import { useProviders } from "@/utils/hooks/useProviders";
import { getZodSchema } from "./form-validation";
import TimeAgo from "react-timeago";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError, KeepApiReadOnlyError } from "@/shared/api";
import { showErrorToast } from "@/shared/ui/utils/showErrorToast";

type ProviderFormProps = {
  provider: Provider;
  onConnectChange?: (isConnecting: boolean, isConnected: boolean) => void;
  closeModal: () => void;
  isProviderNameDisabled?: boolean;
  installedProvidersMode: boolean;
  isLocalhost?: boolean;
};

type KVFormData = Record<string, string>[];
type ProviderFormValue =
  | string
  | number
  | boolean
  | File
  | KVFormData
  | undefined;
type ProviderFormData = Record<string, ProviderFormValue>;
type InputErrors = Record<string, string>;

function dec2hex(dec: number) {
  return ("0" + dec.toString(16)).substring(-2);
}

function generateRandomString() {
  var array = new Uint32Array(56 / 2);
  window.crypto.getRandomValues(array);
  return Array.from(array, dec2hex).join("");
}

function sha256(plain: string) {
  // returns promise ArrayBuffer
  const encoder = new TextEncoder();
  const data = encoder.encode(plain);
  return window.crypto.subtle.digest("SHA-256", data);
}

function base64urlencode(a: ArrayBuffer) {
  var str = "";
  var bytes = new Uint8Array(a);
  var len = bytes.byteLength;
  for (var i = 0; i < len; i++) {
    str += String.fromCharCode(bytes[i]);
  }
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function getConfigsFromArr(arr: [string, ProviderAuthConfig][]) {
  const configs: Provider["config"] = {};
  arr.forEach(([key, value]) => (configs[key] = value));
  return configs;
}

function getRequiredConfigs(config: Provider["config"]): Provider["config"] {
  const configs = Object.entries(config).filter(
    ([_, config]) => config.required && !config.config_main_group
  );
  return getConfigsFromArr(configs);
}

function getOptionalConfigs(config: Provider["config"]): Provider["config"] {
  const configs = Object.entries(config).filter(
    ([_, config]) =>
      !config.required && !config.hidden && !config.config_main_group
  );
  return getConfigsFromArr(configs);
}

function getConfigGroup(type: "config_main_group" | "config_sub_group") {
  return (configs: Provider["config"]) => {
    return Object.entries(configs).reduce(
      (acc: Record<string, Provider["config"]>, [key, config]) => {
        const group = config[type];
        if (!group) return acc;
        acc[group] ??= {};
        acc[group][key] = config;
        return acc;
      },
      {}
    );
  };
}

const getConfigByMainGroup = getConfigGroup("config_main_group");
const getConfigBySubGroup = getConfigGroup("config_sub_group");

function getInitialFormValues(provider: Provider) {
  const initialValues: ProviderFormData = {
    provider_id: provider.id,
    install_webhook: provider.can_setup_webhook ?? false,
    pulling_enabled: provider.pulling_enabled,
  };

  Object.assign(initialValues, {
    provider_name: provider.details?.name,
    ...provider.details?.authentication,
  });

  // Set default values for select & switch inputs
  for (const [field, config] of Object.entries(provider.config)) {
    if (field in initialValues) continue;
    if (config.default === null) continue;
    if (config.type && ["select", "switch"].includes(config.type))
      initialValues[field] = config.default;
  }

  return initialValues;
}

const providerNameFieldConfig: ProviderAuthConfig = {
  required: true,
  description: "Provider Name",
  placeholder: "Enter provider name",
  default: null,
};

const ProviderForm = ({
  provider,
  onConnectChange,
  closeModal,
  isProviderNameDisabled,
  installedProvidersMode,
  isLocalhost,
}: ProviderFormProps) => {
  console.log("Loading the ProviderForm component");
  const { mutate } = useProviders();
  const searchParams = useSearchParams();
  const [formValues, setFormValues] = useState<ProviderFormData>(() =>
    getInitialFormValues(provider)
  );
  const [formErrors, setFormErrors] = useState<string | null>(null);
  const [inputErrors, setInputErrors] = useState<InputErrors>({});
  // Related to scopes
  const [providerValidatedScopes, setProviderValidatedScopes] = useState<{
    [key: string]: boolean | string;
  }>(provider.validatedScopes);
  const [refreshLoading, setRefreshLoading] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const requiredConfigs = useMemo(
    () => getRequiredConfigs(provider.config),
    [provider]
  );
  const optionalConfigs = useMemo(
    () => getOptionalConfigs(provider.config),
    [provider]
  );
  const groupedConfigs = useMemo(
    () => getConfigByMainGroup(provider.config),
    [provider]
  );
  const zodSchema = useMemo(
    () => getZodSchema(provider.config, provider.installed),
    [provider]
  );

  const api = useApi();

  function installWebhook(provider: Provider) {
    return toast.promise(
      api
        .post(`/providers/install/webhook/${provider.type}/${provider.id}`)
        .catch((error) => Promise.reject({ data: error })),
      {
        pending: "Webhook installing 🤞",
        success: `${provider.type} webhook installed 👌`,
        error: {
          render({ data }) {
            // When the promise reject, data will contains the error
            return `Webhook installation failed 😢 Error: ${
              (data as any).message
            }`;
          },
        },
      },
      {
        position: toast.POSITION.TOP_LEFT,
      }
    );
  }

  const callInstallWebhook = async () => await installWebhook(provider);

  async function handleOauth() {
    const verifier = generateRandomString();
    cookieCutter.set("verifier", verifier);
    cookieCutter.set(
      "oauth2_install_webhook",
      formValues.install_webhook?.toString() ?? "false"
    );
    cookieCutter.set(
      "oauth2_pulling_enabled",
      formValues.pulling_enabled?.toString() ?? "false"
    );
    const verifierChallenge = base64urlencode(await sha256(verifier));

    let oauth2Url = provider.oauth2_url;
    const domain = searchParams?.get("domain");
    if (domain) {
      // TODO: this is a hack for Datadog OAuth2 since it can be initiated from different domains
      oauth2Url = oauth2Url?.replace("datadoghq.com", domain);
    }

    let url = `${oauth2Url}&redirect_uri=${window.location.origin}/providers/oauth2/${provider.type}&code_challenge=${verifierChallenge}&code_challenge_method=S256`;

    if (provider.type === "slack") {
      url += `&state=${verifier}`;
    }

    window.location.assign(url);
  }

  function revalidateScopes() {
    setRefreshLoading(true);
    api
      .post(`/providers/${provider.id}/scopes`)
      .then((newValidatedScopes) => {
        setProviderValidatedScopes(newValidatedScopes);
        provider.validatedScopes = newValidatedScopes;
        mutate();
        setRefreshLoading(false);
      })
      .catch((error: any) => {
        showErrorToast(error, "Failed to revalidate scopes");
        setRefreshLoading(false);
      });
  }

  async function deleteProvider() {
    if (confirm("Are you sure you want to delete this provider?")) {
      api
        .delete(`/providers/${provider.type}/${provider.id}`)
        .then(() => {
          mutate();
          closeModal();
        })
        .catch((error: any) => {
          showErrorToast(error, `Failed to delete ${provider.type} 😢`);
        });
    }
  }

  function handleFormChange(key: string, value: ProviderFormValue) {
    if (typeof value === "string" && value.trim().length === 0) {
      // remove fields with empty string value
      setFormValues((prev) => {
        const updated = structuredClone(prev);
        delete updated[key];
        return updated;
      });
    } else {
      setFormValues((prev) => {
        const prevValue = prev[key];
        const updatedValues = {
          ...prev,
          [key]:
            Array.isArray(value) && Array.isArray(prevValue)
              ? [...value]
              : value,
        };
        return updatedValues;
      });
    }

    if (
      value == undefined ||
      typeof value === "boolean" ||
      (typeof value === "object" && value instanceof File === false)
    )
      return;

    const isValid = validate({ [key]: value });
    if (isValid) {
      const updatedInputErrors = { ...inputErrors };
      delete updatedInputErrors[key];
      setInputErrors(updatedInputErrors);
    }
  }

  const handleWebhookChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const checked = event.target.checked;
    setFormValues((prevValues) => ({
      ...prevValues,
      install_webhook: checked,
    }));
  };

  function validate(data?: ProviderFormData) {
    let schema = zodSchema;
    if (data) {
      schema = zodSchema.pick(
        Object.fromEntries(Object.keys(data).map((field) => [field, true]))
      );
    }
    const validation = schema.safeParse(data ?? formValues);
    if (validation.success) return true;
    const errors: InputErrors = {};
    Object.entries(validation.error.format()).forEach(([field, err]) => {
      err && typeof err === "object" && !Array.isArray(err)
        ? (errors[field] = err._errors[0])
        : null;
    });
    setInputErrors(errors);
    return false;
  }

  const handlePullingEnabledChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const checked = event.target.checked;
    setFormValues((prevValues) => ({
      ...prevValues,
      pulling_enabled: checked,
    }));
  };

  async function submit(requestUrl: string, method: string = "POST") {
    const headers: Record<string, string> = {};

    let body;
    if (Object.values(formValues).some((value) => value instanceof File)) {
      // FormData for file uploads
      let formData = new FormData();
      for (let key in formValues) {
        const value = formValues[key];
        if (!value) continue;
        value instanceof File
          ? formData.append(key, value)
          : formData.append(key, value.toString());
      }
      body = formData;
    } else {
      // Standard JSON for non-file submissions
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(formValues);
    }

    return api.request(requestUrl, {
      method: method,
      headers: headers,
      body: body,
    });
  }

  async function handleSubmitError(apiError: unknown) {
    if (apiError instanceof KeepApiReadOnlyError) {
      setFormErrors("You're in read-only mode");
      return;
    }
    if (apiError instanceof KeepApiError === false) return;
    const data = apiError.responseJson;
    const status = apiError.statusCode;
    const error =
      "detail" in data ? data.detail : "message" in data ? data.message : data;
    if (status === 409) {
      setFormErrors(
        `Provider with name ${formValues.provider_name} already exists`
      );
    } else if (status === 412) {
      setProviderValidatedScopes(error);
      setFormErrors(
        `${provider.type} scopes are invalid: ${JSON.stringify(error, null, 4)}`
      );
    } else {
      setApiError(
        typeof error === "object" ? JSON.stringify(error) : error.toString()
      );
    }
  }

  function setApiError(error: string) {
    if (error.includes("SyntaxError")) {
      setFormErrors(
        "Bad response from API: Check the backend logs for more details"
      );
    } else if (error.includes("Failed to fetch")) {
      setFormErrors(
        "Failed to connect to API: Check provider settings and your internet connection"
      );
    } else {
      setFormErrors(error);
    }
  }

  async function handleUpdateClick() {
    if (provider.webhook_required) callInstallWebhook();
    if (!validate()) return;
    setIsLoading(true);
    submit(`/providers/${provider.id}`, "PUT")
      .then(() => {
        setIsLoading(false);
        toast.success("Updated provider successfully", {
          position: "top-left",
        });
        mutate();
      })
      .catch((error) => {
        showErrorToast("Failed to update provider");
        handleSubmitError(error);
        setIsLoading(false);
      });
  }

  async function handleConnectClick() {
    if (!validate()) return;
    setIsLoading(true);
    onConnectChange?.(true, false);
    submit(`/providers/install`)
      .then(async (data) => {
        console.log("Connect Result:", data);
        setIsLoading(false);
        onConnectChange?.(false, true);
        if (
          formValues.install_webhook &&
          provider.can_setup_webhook &&
          !isLocalhost
        ) {
          // mutate after webhook installation
          await installWebhook(data as Provider);
        }
        mutate();
      })
      .catch((error) => {
        handleSubmitError(error);
        setIsLoading(false);
        onConnectChange?.(false, false);
      });
  }

  const installOrUpdateWebhookEnabled = provider.scopes
    ?.filter((scope) => scope.mandatory_for_webhook)
    .every((scope) => providerValidatedScopes[scope.name] === true);

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
              title=""
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
        {provider.scopes && provider.scopes.length > 0 && (
          <ProviderFormScopes
            provider={provider}
            validatedScopes={providerValidatedScopes}
            refreshLoading={refreshLoading}
            onRevalidate={revalidateScopes}
          />
        )}
        <form>
          <div className="form-group">
            {provider.oauth2_url && !provider.installed ? (
              <>
                <Button
                  type="button"
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
                <FormField
                  id="provider_name"
                  config={providerNameFieldConfig}
                  value={(formValues["provider_name"] ?? "").toString()}
                  error={inputErrors["provider_name"]}
                  disabled={isProviderNameDisabled ?? false}
                  title={
                    isProviderNameDisabled
                      ? "This field is disabled because it is pre-filled from the workflow."
                      : ""
                  }
                  onChange={handleFormChange}
                />
              </>
            )}
          </div>
          {/* Render required fields */}
          {Object.entries(requiredConfigs).map(([field, config]) => (
            <div className="mt-2.5" key={field}>
              <FormField
                id={field}
                config={config}
                value={formValues[field]}
                error={inputErrors[field]}
                disabled={provider.provisioned ?? false}
                onChange={handleFormChange}
              />
            </div>
          ))}

          {/* Render grouped fields */}
          {Object.entries(groupedConfigs).map(([name, fields]) => (
            <React.Fragment key={name}>
              <GroupFields
                groupName={name}
                fields={fields}
                data={formValues}
                errors={inputErrors}
                disabled={provider.provisioned ?? false}
                onChange={handleFormChange}
              />
            </React.Fragment>
          ))}

          {/* Render optional fields in a card */}
          {Object.keys(optionalConfigs).length > 0 && (
            <Accordion className="mt-4" defaultOpen={true}>
              <AccordionHeader>Provider Optional Settings</AccordionHeader>
              <AccordionBody>
                <Card>
                  {Object.entries(optionalConfigs).map(([field, config]) => (
                    <div className="mt-2.5" key={field}>
                      <FormField
                        id={field}
                        config={config}
                        value={formValues[field]}
                        error={inputErrors[field]}
                        disabled={provider.provisioned ?? false}
                        onChange={handleFormChange}
                      />
                    </div>
                  ))}
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
                      "install_webhook" in formValues &&
                      typeof formValues["install_webhook"] === "boolean" &&
                      formValues["install_webhook"] &&
                      !isLocalhost
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
                    checked={Boolean(formValues["pulling_enabled"])}
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
                      title=""
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
                  checked={Boolean(formValues["pulling_enabled"])}
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
                type="button"
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

function GroupFields({
  groupName,
  fields,
  data,
  errors,
  disabled,
  onChange,
}: {
  groupName: string;
  fields: Provider["config"];
  data: ProviderFormData;
  errors: InputErrors;
  disabled: boolean;
  onChange: (key: string, value: ProviderFormValue) => void;
}) {
  const subGroups = useMemo(() => getConfigBySubGroup(fields), [fields]);

  if (Object.keys(subGroups).length === 0) {
    // If no subgroups, render fields directly
    return (
      <Card className="mt-4">
        <Title className="capitalize"> {groupName} </Title>
        {Object.entries(fields).map(([field, config]) => (
          <div className="mt-2.5" key={field}>
            <FormField
              id={field}
              config={config}
              value={data[field]}
              error={errors[field]}
              disabled={disabled}
              onChange={onChange}
            />
          </div>
        ))}
      </Card>
    );
  }

  return (
    <Card className="mt-4">
      <Title className="capitalize">{groupName}</Title>
      <TabGroup className="mt-2">
        <TabList>
          {Object.keys(subGroups).map((name) => (
            <Tab key={name} className="capitalize">
              {name}
            </Tab>
          ))}
        </TabList>
        <TabPanels>
          {Object.entries(subGroups).map(([name, subGroup]) => (
            <TabPanel key={name}>
              {Object.entries(subGroup).map(([field, config]) => (
                <div className="mt-2.5" key={field}>
                  <FormField
                    id={field}
                    config={config}
                    value={data[field]}
                    error={errors[field]}
                    disabled={disabled}
                    onChange={onChange}
                  />
                </div>
              ))}
            </TabPanel>
          ))}
        </TabPanels>
      </TabGroup>
    </Card>
  );
}

function FormField({
  id,
  config,
  value,
  error,
  disabled,
  title,
  onChange,
}: {
  id: string;
  config: ProviderAuthConfig;
  value: ProviderFormValue;
  error?: string;
  disabled: boolean;
  title?: string;
  onChange: (key: string, value: ProviderFormValue) => void;
}) {
  function handleInputChange(event: React.ChangeEvent<HTMLInputElement>) {
    let value;
    const files = event.target.files;
    const name = event.target.name;

    // If the input is a file, retrieve the file object, otherwise retrieve the value
    if (files && files.length > 0) {
      value = files[0]; // Assumes single file upload
    } else {
      value = event.target.value;
    }

    onChange(name, value);
  }

  switch (config.type) {
    case "select":
      return (
        <SelectField
          id={id}
          config={config}
          value={value}
          error={error}
          disabled={disabled}
          onChange={(value) => onChange(id, value)}
        />
      );
    case "form":
      return (
        <KVForm
          id={id}
          config={config}
          value={value}
          error={error}
          disabled={disabled}
          onAdd={(data) => onChange(id, data)}
          onChange={(value) => onChange(id, value)}
        />
      );
    case "file":
      return (
        <FileField
          id={id}
          config={config}
          error={error}
          disabled={disabled}
          onChange={handleInputChange}
        />
      );
    case "switch":
      return (
        <SwitchInput
          id={id}
          config={config}
          value={value}
          disabled={disabled}
          onChange={(value) => onChange(id, value)}
        />
      );
    default:
      return (
        <TextField
          id={id}
          config={config}
          value={value}
          error={error}
          disabled={disabled}
          title={title}
          onChange={handleInputChange}
        />
      );
  }
}

function TextField({
  id,
  config,
  value,
  error,
  disabled,
  title,
  onChange,
}: {
  id: string;
  config: ProviderAuthConfig;
  value: ProviderFormValue;
  error?: string;
  disabled: boolean;
  title?: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <>
      <FieldLabel id={id} config={config} />
      <TextInput
        type={config.sensitive ? "password" : "text"}
        id={id}
        name={id}
        value={value?.toString() ?? ""}
        onChange={onChange}
        autoComplete="off"
        error={Boolean(error)}
        errorMessage={error}
        placeholder={config.placeholder ?? `Enter ${id}`}
        disabled={disabled}
        title={title ?? ""}
      />
    </>
  );
}

function SelectField({
  id,
  config,
  value,
  error,
  disabled,
  onChange,
}: {
  id: string;
  config: ProviderAuthConfig;
  value: ProviderFormValue;
  error?: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <>
      <FieldLabel id={id} config={config} />
      <Select
        name={id}
        value={value?.toString() ?? config.default?.toString()}
        onValueChange={onChange}
        placeholder={config.placeholder || `Select ${id}`}
        error={Boolean(error)}
        errorMessage={error}
        disabled={disabled}
      >
        {config.options?.map((option) => (
          <SelectItem key={option} value={option.toString()}>
            {option}
          </SelectItem>
        ))}
      </Select>
    </>
  );
}

function FileField({
  id,
  config,
  disabled,
  error,
  onChange,
}: {
  id: string;
  config: ProviderAuthConfig;
  disabled: boolean;
  error?: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  const [selected, setSelected] = useState<string>();
  const ref = useRef<HTMLInputElement>(null);

  function handleClick(e: React.MouseEvent<HTMLButtonElement>) {
    e.preventDefault();
    if (ref.current) ref.current.click();
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files && e.target.files[0]) {
      setSelected(e.target.files[0].name);
    }
    onChange(e);
  }

  return (
    <>
      <FieldLabel id={id} config={config} />
      <Button
        type="button"
        color="orange"
        size="md"
        icon={ArrowDownOnSquareIcon}
        disabled={disabled}
        onClick={handleClick}
      >
        {selected ? `File Chosen: ${selected}` : `Upload a ${id}`}
      </Button>
      <input
        type="file"
        ref={ref}
        id={id}
        name={id}
        accept={config.file_type}
        style={{ display: "none" }}
        onChange={handleChange}
        disabled={disabled}
      />
      {error && error?.length > 0 && (
        <p className="text-sm text-red-500 mt-1">{error}</p>
      )}
    </>
  );
}

function KVForm({
  id,
  config,
  value,
  error,
  disabled,
  onAdd,
  onChange,
}: {
  id: string;
  config: ProviderAuthConfig;
  value: ProviderFormValue;
  error?: string;
  disabled: boolean;
  onAdd: (data: KVFormData) => void;
  onChange: (value: KVFormData) => void;
}) {
  function handleAdd() {
    const newData = Array.isArray(value)
      ? [...value, { key: "", value: "" }]
      : [{ key: "", value: "" }];
    onAdd(newData);
  }

  return (
    <div>
      <div className="flex items-center mb-2">
        <FieldLabel id={id} config={config} />
        <Button
          type="button"
          className="ml-2"
          icon={PlusIcon}
          variant="secondary"
          color="orange"
          size="xs"
          onClick={handleAdd}
          disabled={disabled}
        >
          Add Entry
        </Button>
      </div>
      {Array.isArray(value) && <KVInput data={value} onChange={onChange} />}
      {error && error?.length > 0 && (
        <p className="text-sm text-red-500 mt-1">{error}</p>
      )}
    </div>
  );
}

const KVInput = ({
  data,
  onChange,
}: {
  data: KVFormData;
  onChange: (entries: KVFormData) => void;
}) => {
  const handleEntryChange = (index: number, name: string, value: string) => {
    const newEntries = data.map((entry, i) =>
      i === index ? { ...entry, [name]: value } : entry
    );
    onChange(newEntries);
  };

  const removeEntry = (index: number) => {
    const newEntries = data.filter((_, i) => i !== index);
    onChange(newEntries);
  };

  return (
    <div>
      {data.map((entry, index) => (
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
            type="button"
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

function SwitchInput({
  id,
  config,
  value,
  disabled,
  onChange,
}: {
  id: string;
  config: ProviderAuthConfig;
  value: ProviderFormValue;
  disabled?: boolean;
  onChange: (value: boolean) => void;
}) {
  if (typeof value !== "boolean") return null;

  return (
    <div className="flex justify-between">
      <FieldLabel id={id} config={config} />
      <Switch checked={value} disabled={disabled} onChange={onChange} />
    </div>
  );
}

function FieldLabel({
  id,
  config,
}: {
  id: string;
  config: ProviderAuthConfig;
}) {
  return (
    <label htmlFor={id} className="flex items-center mb-1">
      <Text className="capitalize">
        {config.description}
        {config.required === true && <span className="text-red-400">*</span>}
      </Text>
      {config.hint && (
        <Icon
          icon={QuestionMarkCircleIcon}
          variant="simple"
          color="gray"
          size="sm"
          tooltip={`${config.hint}`}
        />
      )}
    </label>
  );
}

export default ProviderForm;
