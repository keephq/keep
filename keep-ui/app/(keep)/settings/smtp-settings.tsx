import { useState } from "react";
import { Card, Button, Title, TextInput } from "@tremor/react";
import useSWR from "swr";
import Loading from "@/app/(keep)/loading";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/api";
import { PageTitle } from "@/shared/ui";
import { PageSubtitle } from "@/shared/ui";
import { useTranslations } from "next-intl";

interface SMTPSettings {
  host: string;
  port: number;
  username?: string;
  password?: string;
  secure: boolean;
  from_email: string;
  to_email?: string;
}

interface SMTPSettingsErrors {
  host?: string;
  port?: string;
  username?: string;
  password?: string;
  from_email?: string;
  to_email?: string;
}

interface TestResult {
  status: boolean;
  message: string;
  logs: string[];
}

interface Props {
  selectedTab: string;
}

const isValidPort = (port: number) => {
  return !isNaN(port) && port > 0 && port <= 65535;
};

export default function SMTPSettingsForm({ selectedTab }: Props) {
  const t = useTranslations("settings.smtp");
  const [settings, setSettings] = useState<SMTPSettings>({
    host: "",
    port: 25,
    username: "",
    password: "",
    secure: false,
    from_email: "",
    to_email: "",
  });
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [errors, setErrors] = useState<SMTPSettingsErrors>({});
  const [isSaveSuccessful, setSaveSuccessful] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [shouldFetch, setShouldFetch] = useState(true);
  const [smtpInstalled, setSmtpInstalled] = useState(false);
  const [deleteSuccessful, setDeleteSuccessful] = useState(false);
  const api = useApi();

  const validateSaveFields = () => {
    const newErrors: SMTPSettingsErrors = {};
    if (!settings.host) newErrors.host = t("hostRequired");
    if (!isValidPort(settings.port)) newErrors.port = t("portInvalid");
    if (!settings.from_email) newErrors.from_email = t("fromRequired");
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateTestFields = () => {
    const validSave = validateSaveFields();
    if (!settings.to_email)
      setErrors((errors) => ({
        ...errors,
        to_email: t("toRequiredForTesting"),
      }));
    return validSave && settings.to_email;
  };

  const shouldFetchUrl =
    api.isReady() && shouldFetch && selectedTab === "smtp"
      ? "/settings/smtp"
      : null;

  // Use the useSWR hook to fetch the settings
  const {
    data: smtpSettings,
    error,
    isValidating: isLoading,
  } = useSWR(
    shouldFetchUrl, // Update with your actual endpoint
    (url) => api.get(url),
    { revalidateOnFocus: false }
  );

  // Show loading state or error messages if needed
  if (isLoading) {
    return <Loading />;
  }

  // if no errors and we have data, set the settings
  if (smtpSettings) {
    // if the SMTP is not installed yet
    if (Object.keys(smtpSettings).length === 0) {
      // smtpSettings is an empty object, assign default values
      setSettings((previousSettings) => ({
        ...previousSettings, // keep other settings if they exist
        port: 25, // replace with your actual default port value
      }));
    } else {
      // smtp is installed
      setSettings(smtpSettings);
      setSmtpInstalled(true);
    }
    setShouldFetch(false);
  }

  const onDelete = async () => {
    try {
      const response = await api.delete(`/settings/smtp`);
      // If the delete was successful
      setDeleteSuccessful(true);
      setSettings({
        host: "",
        port: 25,
        username: "",
        password: "",
        secure: false,
        from_email: "",
        to_email: "",
      });
    } catch (error) {
      // If the delete failed
      setDeleteSuccessful(false);
      if (error instanceof KeepApiError) {
        setErrorMessage(error.message || t("errorDeleting"));
      } else {
        setErrorMessage(t("unexpectedError"));
      }
    }
  };

  const onSave = async () => {
    if (!validateSaveFields()) return;

    const payload = { ...settings };
    // Remove 'to_email' if it's empty
    if (!payload.to_email) {
      delete payload.to_email; // Remove 'to_email' if it's empty
    }
    try {
      const response = await api.post(`/settings/smtp`, payload);
      // If the save was successful
      setSaveSuccessful(true);
      setSmtpInstalled(true);
    } catch (error) {
      // If the save failed
      setSaveSuccessful(false);
      if (error instanceof KeepApiError) {
        setErrorMessage(error.message || t("errorSaving"));
      } else {
        setErrorMessage(t("unexpectedError"));
      }
    }
  };

  const onTest = async () => {
    try {
      if (!validateTestFields()) return;

      // Prepare the payload with current settings
      const payload = { ...settings };
      // Convert port to number if it's a string
      if (typeof payload.port === "string") {
        payload.port = parseInt(payload.port, 10);
      }

      const result = await api.post(`/settings/smtp/test`, payload);

      setTestResult({
        status: true,
        message: t("success"),
        logs: result.logs || [],
      });
    } catch (error) {
      if (error instanceof KeepApiError) {
        if (error.statusCode === 400) {
          // If status is 400, show message/logs from the response
          const result = error.responseJson;
          setTestResult({
            status: false,
            message: result.message || t("errorOccurred"),
            logs: result.logs || [],
          });
        } else {
          // For any other status, show a static message
          setTestResult({
            status: false,
            message: t("failedToConnect"),
            logs: [],
          });
        }
      } else {
        // If the request fails to reach the server or there's a network error
        setTestResult({
          status: false,
          message: t("failedToConnect"),
          logs: [],
        });
      }
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setSettings({
      ...settings,
      [name]: type === "checkbox" ? checked : value,
    });
    // Also clear errors for that field
    setErrors((prevErrors) => ({
      ...prevErrors,
      [name as keyof SMTPSettingsErrors]: undefined,
    }));
  };

  return (
    <div className="flex flex-col gap-4">
      <header>
        <PageTitle>{t("smtpSettings")}</PageTitle>
        <PageSubtitle>{t("configureSmtp")}</PageSubtitle>
      </header>
      <Card className="p-4">
        <div className="mb-4">
          <label htmlFor="host" className="block text-sm font-medium mb-1">
            {t("host")}
          </label>
          <TextInput
            type="text"
            id="host"
            name="host"
            value={settings.host}
            onChange={handleChange}
            placeholder="smtp.example.com"
            color="orange"
            error={!!errors.host}
          />
          <label className="block text-sm font-medium mb-1 text-gray-500">
            {t("hostDescription")}
          </label>
          {errors.host && (
            <p className="mt-1 text-sm text-red-500">{errors.host}</p>
          )}
        </div>

        <div className="mb-4">
          <label htmlFor="port" className="block text-sm font-medium mb-1">
            {t("port")}
          </label>
          <TextInput
            type="text"
            id="port"
            name="port"
            value={settings.port.toString()}
            onChange={handleChange}
            color="orange"
            error={!!errors.port}
          />
          <label className="block text-sm font-medium mb-1 text-gray-500">
            {t("portDescription")}
          </label>
          {errors.port && (
            <p className="mt-1 text-sm text-red-500">{errors.port}</p>
          )}
        </div>

        <div className="mb-4">
          <label
            htmlFor="from_email"
            className="block text-sm font-medium mb-1"
          >
            {t("fromAddress")}
          </label>
          <TextInput
            type="text"
            id="from_email"
            name="from_email"
            value={settings.from_email}
            onChange={handleChange}
            color="orange"
            error={!!errors.from_email}
            placeholder="keepserver@example.com"
          />
          <label className="block text-sm font-medium mb-1 text-gray-500">
            {t("fromAddressDescription")}
          </label>
          {errors.from_email && (
            <p className="mt-1 text-sm text-red-500">{errors.from_email}</p>
          )}
        </div>

        <div className="mb-4">
          <label htmlFor="username" className="block text-sm font-medium mb-1">
            {t("username")}
          </label>
          <TextInput
            type="text"
            id="username"
            name="username"
            value={settings.username}
            onChange={handleChange}
            color="orange"
            error={!!errors.username}
          />
          <label className="block text-sm font-medium mb-1 text-gray-500">
            {t("usernameDescription")}
          </label>
        </div>

        <div className="mb-4">
          <label htmlFor="password" className="block text-sm font-medium mb-1">
            {t("password")}
          </label>
          <TextInput
            type="password"
            id="password"
            name="password"
            value={settings.password}
            onChange={handleChange}
            color="orange"
            error={!!errors.password}
          />
          <label className="block text-sm font-medium mb-1 text-gray-500">
            {t("passwordDescription")}
          </label>
        </div>

        <div className="mb-4">
          <label className="flex items-center">
            <input
              type="checkbox"
              id="secure"
              name="secure"
              className="form-checkbox"
              checked={settings.secure}
              onChange={handleChange}
            />
            <span className="ml-2 text-sm font-medium">{t("useTls")}</span>
          </label>
        </div>

        <div className="flex flex-col justify-end space-y-2 mt-6">
          <div className="flex justify-end space-x-2">
            <Button onClick={onSave} color="orange" className="px-4 py-2">
              {t("save")}
            </Button>
            <Button
              onClick={onDelete}
              color="orange"
              className="px-4 py-2"
              disabled={!smtpInstalled}
            >
              {t("delete")}
            </Button>
          </div>
          {(isSaveSuccessful === false || deleteSuccessful === false) && (
            <div className="text-red-500 text-sm mt-2">{errorMessage}</div>
          )}
          {isSaveSuccessful === true && (
            <div className="text-green-500 text-sm mt-2">
              {t("settingsSaved")}
            </div>
          )}
          {deleteSuccessful === true && (
            <div className="text-green-500 text-sm mt-2">
              {t("settingsDeleted")}
            </div>
          )}
        </div>
      </Card>

      <Card className="p-4">
        <div className="mb-4">
          <label htmlFor="to_email" className="block text-sm font-medium mb-1">
            {t("to")}
          </label>
          <TextInput
            type="text"
            id="to_email"
            name="to_email"
            value={settings.to_email}
            onChange={handleChange}
            placeholder="recipient@example.com"
            color="orange"
            error={!!errors.to_email}
          />
          <label className="block text-sm font-medium mb-1 text-gray-500">
            {t("toDescription")}
          </label>
          {errors.to_email && (
            <p className="mt-1 text-sm text-red-500">{errors.to_email}</p>
          )}
        </div>
        <div className="flex justify-end space-x-2 mt-6">
          <Button onClick={onTest} color="orange" className="px-4 py-2">
            {t("test")}
          </Button>
        </div>
      </Card>
      {testResult && (
        <Card
          className={`p-4 ${testResult.status ? "bg-green-100" : "bg-red-100"}`}
        >
          <Title>{testResult.status ? t("success") : t("failure")}</Title>
          <div
            className="mt-2 whitespace-pre-wrap"
            style={{ overflowX: "auto" }}
          >
            <strong>{t("message")}</strong>
            <br />
            {testResult.message}
            <br />
            <strong>{t("logs")}</strong>
            <pre style={{ overflowX: "auto" }}>
              {testResult.logs
                ? testResult.logs.join("\n")
                : t("noLogsAvailable")}
            </pre>
          </div>
        </Card>
      )}
    </div>
  );
}
