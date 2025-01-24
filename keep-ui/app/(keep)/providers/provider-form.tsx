import React, { useState, useMemo } from "react";
import {
  Provider,
  ProviderAuthConfig,
  ProviderFormData,
  ProviderFormValue,
  ProviderInputErrors,
} from "./providers";
import Image from "next/image";
import {
  Title,
  Text,
  Button,
  Callout,
  Icon,
  Subtitle,
  Divider,
  Card,
  Accordion,
  AccordionHeader,
  AccordionBody,
  Badge,
  Tab,
  TabList,
  TabGroup,
  TabPanel,
  TabPanels,
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
  GlobeAltIcon,
  DocumentTextIcon,
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
import { useConfig } from "@/utils/hooks/useConfig";
import { KeepApiError, KeepApiReadOnlyError } from "@/shared/api";
import { showErrorToast } from "@/shared/ui";
import {
  base64urlencode,
  generateRandomString,
  sha256,
} from "@/shared/lib/encodings";
import {
  FormField,
  getConfigByMainGroup,
  getOptionalConfigs,
  getRequiredConfigs,
  GroupFields,
} from "./form-fields";
import ProviderLogs from "./provider-logs";
import { DynamicImageProviderIcon } from "@/components/ui";

type ProviderFormProps = {
  provider: Provider;
  onConnectChange?: (isConnecting: boolean, isConnected: boolean) => void;
  closeModal: () => void;
  isProviderNameDisabled?: boolean;
  installedProvidersMode: boolean;
  isLocalhost?: boolean;
};

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
  const [inputErrors, setInputErrors] = useState<ProviderInputErrors>({});
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
  const { data: config } = useConfig();

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
              (data as any).data.responseJson.detail
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
      typeof value === "boolean" ||
      (typeof value === "object" && value instanceof File === false)
    )
      return;

    const isValid = validate({
      [key]:
        typeof value === "string" && value.length === 0 ? undefined : value,
    });
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
    const errors: ProviderInputErrors = {};
    Object.entries(validation.error.format()).forEach(([field, err]) => {
      err && typeof err === "object" && !Array.isArray(err)
        ? (errors[field] = err._errors[0])
        : null;
    });
    setInputErrors((prev) => ({ ...prev, ...errors }));
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

  const [activeTab, setActiveTab] = useState(0);

  const renderFormContent = () => (
    <>
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
          <div
            className={`${
              isLocalhost ? "bg-gray-100 p-2 rounded-tremor-default" : ""
            }`}
          >
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
              <label htmlFor="install_webhook" className="flex items-center">
                <Text className="capitalize">Install Webhook</Text>
                <Icon
                  icon={QuestionMarkCircleIcon}
                  variant="simple"
                  color="gray"
                  size="sm"
                  tooltip={`Whether to install Keep as a webhook integration in ${provider.type}. This allows Keep to asynchronously receive alerts from ${provider.type}. Please note that this will install a new integration in ${provider.type} and slightly modify your monitors/notification policy to include Keep.`}
                />
              </label>
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
            {isLocalhost && (
              <span className="text-sm">
                <Callout
                  title=""
                  className="mt-4"
                  icon={ExclamationTriangleIcon}
                  color="gray"
                >
                  <a
                    href={`${
                      config?.KEEP_DOCS_URL || "https://docs.keephq.dev"
                    }/development/external-url`}
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
            disabled={!installOrUpdateWebhookEnabled || provider.provisioned}
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

      <input type="hidden" name="providerId" value={provider.id} />
    </>
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex-grow overflow-auto p-5">
        <div className="flex flex-row">
          <Title>Connect to {provider.display_name}</Title>
          {provider.provisioned && (
            <Badge color="orange" className="ml-2">
              Provisioned
            </Badge>
          )}
          <Link
            href={`${
              config?.KEEP_DOCS_URL || "http://docs.keephq.dev"
            }/providers/documentation/${provider.type}-provider`}
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
            <DynamicImageProviderIcon
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

        {installedProvidersMode ? (
          <TabGroup className="mt-4">
            <TabList>
              <Tab>Configuration</Tab>
              <Tab>Logs</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <form className="mt-4">{renderFormContent()}</form>
              </TabPanel>
              <TabPanel className="h-full">
                <div className="h-[600px]">
                  <ProviderLogs providerId={provider.id} />
                </div>
              </TabPanel>
            </TabPanels>
          </TabGroup>
        ) : (
          <form className="mt-4">{renderFormContent()}</form>
        )}
      </div>

      <div className="flex justify-end p-5 border-t">
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
