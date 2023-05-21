// @ts-nocheck
'use client';
import React, { useState } from 'react';
import {  useSession } from 'next-auth/react';
import { Provider } from './provider-row';
import './provider-form.css';

type ProviderFormProps = {
  provider: Provider;
  formData: Record<string, string>; // New prop for form data
  onFormChange: (formValues: Record<string, string>) => void;
};

const ProviderForm = ({ provider, formData, onFormChange }: ProviderFormProps) => {
  console.log("Loading the ProviderForm component");
  const [formValues, setFormValues] = useState<{ [key: string]: string }>({
    provider_id: provider.id, // Include the provider ID in formValues
    ...formData,
  });
  const [formErrors, setFormErrors] = useState({});
  const [testResult, setTestResult] = useState('');
  const [connectResult, setConnectResult] = useState('');
  const [alertData, setAlertData] = useState([]);
  const [isConnected, setIsConnected] = useState(false);

  const { data: session, status, update } = useSession()
  // @ts-ignore
  if(!session?.id_token){
    console.log("No session id_token, refreshing session from the server");
    update();
  }
  // update();
  // TODO - fix the typing here
  // @ts-ignore
  const id_token = session?.id_token;

  // @ts-ignore
  const validateForm = (updatedFormValues) => {
    const errors = {};
    for (const method of provider.authentication) {
      if (method.placeholder && !formValues[method.name]) {
        // @ts-ignore
        errors[method.name] = true;
      }
      // @ts-ignore
      if ('validation' in method && formValues[method.name] && !method.validation(updatedFormValues[method.name])) {
        // @ts-ignore
        errors[method.name] = true;
      }
    }
    markErrors(errors);
    return errors;
  };


  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setFormValues((prevValues) => ({ ...prevValues, [name]: value }));
    setFormErrors((prevErrors) => ({ ...prevErrors, [name]: false }));
    const updatedFormValues = { ...formValues, [name]: value };
    onFormChange(updatedFormValues);
    validateForm(updatedFormValues);
  };

  const markErrors = (errors: Record<string, boolean>) => {
    const inputElements = document.querySelectorAll('.form-group input');
    inputElements.forEach((input) => {
      const name = input.getAttribute('name');
      // @ts-ignore
      if (errors[name]) {
        input.classList.add('error');
      } else {
        input.classList.remove('error');
      }
    });
  };
  const validateAndSubmit = (requestUrl: string): Promise<any> => {
    return new Promise((resolve, reject) => {
      const errors = validateForm(formValues);
      if (Object.keys(errors).length === 0) {
        markErrors(errors);
        fetch(requestUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${id_token}`,
          },
          body: JSON.stringify(formValues),
        })
          .then((response) => {
            if (response.ok) {
              console.log("response ok")
              return response.json();
            } else {
              console.log("response not ok")
              throw new Error(response.statusText);
            }
          })
          .then((data) => {
            resolve(data);
            setFormErrors({});
          })
          .catch((error) => {
            reject(error);
            console.error('Error:', error);
          });
      } else {
        setFormErrors(errors);
        markErrors(errors);
        reject(new Error('Form validation failed'));
      }
    });
  };

  const handleTestClick = async () => {
    try {
      const data = await validateAndSubmit(process.env.NEXT_PUBLIC_TEST_PROVIDER_URL!);
      if (data && data.alerts) {
        console.log("Test succeessful")
        setTestResult('success');
        setAlertData(data.alerts);
      } else {
        setTestResult('error');
      }
    } catch (error) {
      console.error('Test failed:', error);
    }
  };


  const handleConnectClick = () => {
    validateAndSubmit(process.env.NEXT_PUBLIC_INSTALL_PROVIDER_URL!)
      .then((data) => {
        console.log('Connect Result:', data);
        setConnectResult(data.result);
        setIsConnected(true);
      })
      .catch((error) => {
        console.error('Connect failed:', error);
      });
  };
  console.log("ProviderForm component loaded");

  return (
    <div>
      <form className={isConnected ? 'connected-form' : ''}>
        {provider.authentication.map((method) => (
          <div className="form-group" key={method.name}>
            <label htmlFor={method.name}>{method.desc}:</label>
            <input
              type={method.type}
              id={method.name}
              name={method.name}
              value={formValues[method.name] || ''}
              onChange={handleInputChange}
              placeholder={method.placeholder}
              disabled={isConnected} // Disable the field when isConnected is true
            />
          </div>
        ))}
        {/* Hidden input for provider ID */}
        <input type="hidden" name="providerId" value={provider.id} />
        <div className="button-group">
          <button type="button" className="test-button" onClick={handleTestClick}>
            Test
          </button>
          <button type="button" className="connect-button" onClick={handleConnectClick}>
            Connect
          </button>
        </div>
      </form>
      {formErrors.error && (
        <div className="error-message">
          Error: {formErrors.error}
        </div>
      )}
      {testResult === 'success' && (
        <div>
          <div className="test-result">Test Result: {testResult}</div>
          <table className="alerts-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Title</th>
                <th>Condition</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {alertData.map((alert) => (
                <tr key={alert.id}>
                  <td>{alert.id}</td>
                  <td>{alert.title}</td>
                  <td>{alert.condition}</td>
                  <td>{alert.updated}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default ProviderForm;
