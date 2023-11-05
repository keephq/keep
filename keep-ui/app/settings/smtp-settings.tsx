import { useState } from 'react';
import { Card, Button, Title, Subtitle, TextInput } from '@tremor/react';
import { getApiURL } from "utils/apiUrl";

interface SMTPSettings {
  host: string;
  port: number;
  username: string;
  password: string;
  secure: boolean;
}

interface TestResult {
  status: boolean;
  message: string;
  logs: string[];
}

interface Props {
  accessToken: string;
}

export default function SMTPSettingsForm({ accessToken }: Props) {
  const [settings, setSettings] = useState<SMTPSettings>({
    host: '',
    port: 587,
    username: '',
    password: '',
    secure: false,
  });
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  const apiUrl = getApiURL();
  const onSave = async () => {
    // Logic to save the SMTP settings
  };

  const onTest = async () => {
    try {
      const response = await fetch(`${apiUrl}/settings/smtp/test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify(settings),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      setTestResult(result);
    } catch (error) {
      setTestResult({
        status: false,
        message: 'Failed to connect to server or process the request.',
        logs: ['No logs to display.']
      });
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setSettings({
      ...settings,
      [name]: type === 'checkbox' ? checked : value,
    });
  };

  return (
    <div className='p-6'>
      <Title>SMTP Settings</Title>
      <Subtitle>Configure your SMTP server to send emails</Subtitle>
      <Card className='mt-4 p-4'>
        <div className="mb-4">
          <label htmlFor="host" className="block text-sm font-medium mb-1">Host</label>
          <TextInput
            type="text"
            id="host"
            name="host"
            value={settings.host}
            onChange={handleChange}
            placeholder='smtp.example.com'
            color="orange"
          />
        </div>

        <div className="mb-4">
          <label htmlFor="port" className="block text-sm font-medium mb-1">Port</label>
          <TextInput
            type="text"
            id="port"
            name="port"
            value={settings.port.toString()}
            onChange={handleChange}
            color="orange"
          />
        </div>

        <div className="mb-4">
          <label htmlFor="username" className="block text-sm font-medium mb-1">Username</label>
          <TextInput
            type="text"
            id="username"
            name="username"
            value={settings.username}
            onChange={handleChange}
            color="orange"
          />
        </div>

        <div className="mb-4">
          <label htmlFor="password" className="block text-sm font-medium mb-1">Password</label>
          <TextInput
            type="password"
            id="password"
            name="password"
            value={settings.password}
            onChange={handleChange}
            color="orange"
          />
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
            <span className="ml-2 text-sm font-medium">Use SSL/TLS</span>
          </label>
        </div>

        <div className='flex justify-end space-x-2 mt-6'>
          <Button onClick={onTest} color="orange">
            Test
          </Button>
          <Button onClick={onSave} color="orange">
            Update
          </Button>
        </div>
      </Card>
      {testResult && (
        <Card className={`mt-4 p-4 ${testResult.status ? 'bg-green-100' : 'bg-red-100'}`}>
          <Title>{testResult.status ? 'Success' : 'Failure'}</Title>
          <div className="mt-2 whitespace-pre-wrap">
            <strong>Message:</strong> {testResult.message}
            <br />
            <strong>Logs:</strong>
            <pre>{testResult.logs ? testResult.logs.join('\n') : 'No logs available.'}</pre>
          </div>
        </Card>
      )}
    </div>
  );
}
