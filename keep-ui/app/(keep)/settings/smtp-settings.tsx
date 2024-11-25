import { useState } from "react";
import { Card, Button, Title, Subtitle, TextInput } from "@tremor/react";
import useSWR from "swr";
import Loading from "@/app/(keep)/loading";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/lib/api/KeepApiError";

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
    if (!settings.host) newErrors.host = "Host is required";
    if (!isValidPort(settings.port)) newErrors.port = "Port is invalid";
    if (!settings.from_email) newErrors.from_email = "From is required";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateTestFields = () => {
    const validSave = validateSaveFields();
    if (!settings.to_email)
      setErrors((errors) => ({
        ...errors,
        to_email: "To is required for testing",
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
    api.get,
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
        setErrorMessage(error.message || "An error occurred while deleting.");
      } else {
        setErrorMessage("An unexpected error occurred");
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
        setErrorMessage(error.message || "An error occurred while saving.");
      } else {
        setErrorMessage("An unexpected error occurred");
      }
    }
  };

  const onTest = async () => {
    try {
      if (!validateTestFields()) return;
      const result = await api.post(`/settings/smtp/test`);

      setTestResult({
        status: true,
        message: "Success!",
        logs: result.logs || [],
      });
    } catch (error) {
      if (error instanceof KeepApiError) {
        if (error.statusCode === 400) {
          // If status is 400, show message/logs from the response
          const result = error.responseJson;
          setTestResult({
            status: false,
            message: result.message || "Error occurred.",
            logs: result.logs || [],
          });
        } else {
          // For any other status, show a static message
          setTestResult({
            status: false,
            message: "Failed to connect to server or process the request.",
            logs: [],
          });
        }
      } else {
        // If the request fails to reach the server or there's a network error
        setTestResult({
          status: false,
          message: "Failed to connect to server or process the request.",
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
    <div className="mt-10">
      <Title>SMTP Settings</Title>
      <Subtitle>Configure your SMTP server to send emails</Subtitle>
      <Card className="mt-4 p-4">
        <div className="mb-4">
          <label htmlFor="host" className="block text-sm font-medium mb-1">
            Host
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
            The SMTP host name of your mail server.
          </label>
          {errors.host && (
            <p className="mt-1 text-sm text-red-500">{errors.host}</p>
          )}
        </div>

        <div className="mb-4">
          <label htmlFor="port" className="block text-sm font-medium mb-1">
            Port
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
            SMTP port number to use. Default is 25.
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
            From address
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
            The default address this server will use to send the emails from.
          </label>
          {errors.from_email && (
            <p className="mt-1 text-sm text-red-500">{errors.from_email}</p>
          )}
        </div>

        <div className="mb-4">
          <label htmlFor="username" className="block text-sm font-medium mb-1">
            Username
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
            Optional - if you use authenticated SMTP, enter your username.
          </label>
        </div>

        <div className="mb-4">
          <label htmlFor="password" className="block text-sm font-medium mb-1">
            Password
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
            Optional - if you use authenticated SMTP, enter your password.
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
            <span className="ml-2 text-sm font-medium">Use TLS</span>
          </label>
        </div>

        <div className="flex flex-col justify-end space-y-2 mt-6">
          <div className="flex justify-end space-x-2">
            <Button onClick={onSave} color="orange" className="px-4 py-2">
              Save
            </Button>
            <Button
              onClick={onDelete}
              color="orange"
              className="px-4 py-2"
              disabled={!smtpInstalled}
            >
              Delete
            </Button>
          </div>
          {(isSaveSuccessful === false || deleteSuccessful === false) && (
            <div className="text-red-500 text-sm mt-2">{errorMessage}</div>
          )}
          {isSaveSuccessful === true && (
            <div className="text-green-500 text-sm mt-2">
              SMTP settings saved successfully.
            </div>
          )}
          {deleteSuccessful === true && (
            <div className="text-green-500 text-sm mt-2">
              SMTP settings deleted successfully.
            </div>
          )}
        </div>
      </Card>

      <Card className="mt-8 p-4">
        <div className="mb-4">
          <label htmlFor="to_email" className="block text-sm font-medium mb-1">
            To:
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
            A test mail address. Keep will try to send email to this address.
          </label>
          {errors.to_email && (
            <p className="mt-1 text-sm text-red-500">{errors.to_email}</p>
          )}
        </div>
        <div className="flex justify-end space-x-2 mt-6">
          <Button onClick={onTest} color="orange" className="px-4 py-2">
            Test
          </Button>
        </div>
      </Card>
      {testResult && (
        <Card
          className={`mt-4 p-4 ${
            testResult.status ? "bg-green-100" : "bg-red-100"
          }`}
        >
          <Title>{testResult.status ? "Success" : "Failure"}</Title>
          <div
            className="mt-2 whitespace-pre-wrap"
            style={{ overflowX: "auto" }}
          >
            <strong>Message:</strong>
            <br />
            {testResult.message}
            <br />
            <strong>Logs:</strong>
            <pre style={{ overflowX: "auto" }}>
              {testResult.logs
                ? testResult.logs.join("\n")
                : "No logs available."}
            </pre>
          </div>
        </Card>
      )}
    </div>
  );
}
