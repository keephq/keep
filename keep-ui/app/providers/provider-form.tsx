// @ts-nocheck
import React, { useState } from "react";
import { useSession } from "../../utils/customAuth";
import { Provider } from "./providers";
import { Provider } from "./providers";
import { getApiURL } from "../../utils/apiUrl";
import Alert from "./alert";
import { FaQuestionCircle } from "react-icons/fa";
import "./provider-form.css";

type ProviderFormProps = {
  provider: Provider;
  formData: Record<string, string>; // New prop for form data
  formErrorsData: Record<string, string>; // New prop for form data
  onFormChange: (formValues: Record<string, string>, formErrors: Record<string, string>) => void;
  onConnectChange: (isConnecting: boolean, isConnected: boolean) => void;
  onAddProvider: (provider: Provider) => void;
};

const ProviderForm = ({
  provider,
  formData,
  formErrorsData,
  onFormChange,
  onConnectChange,
  onAddProvider
}: ProviderFormProps) => {
  console.log("Loading the ProviderForm component");
  const [formValues, setFormValues] = useState<{ [key: string]: string }>({
    provider_id: provider.id, // Include the provider ID in formValues
    ...formData,
  });
  const [formErrors, setFormErrors] = useState<{ [key: string]: string }>({
    ...formErrorsData,
  });
  const [testResult, setTestResult] = useState("");
  const [alertData, setAlertData] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const { data: session, status, update } = useSession();


  const [hoveredLabel, setHoveredLabel] = useState(null);

  const handleLabelMouseEnter = (labelKey) => {
    setHoveredLabel(labelKey);
  };

  const handleLabelMouseLeave = (labelKey) => {
    setHoveredLabel(null);
  };
  // @ts-ignore
  const accessToken = session?.accessToken;

  // @ts-ignore
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
      if(!formValues.provider_name){
        errors["provider_name"] = true;
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
    validateForm(updatedFormValues);
    onFormChange(updatedFormValues, formErrors);
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
            throw new Error(`Error: ${response.status}, ${JSON.stringify(errorData)}`);
          });
        }
        return response.json();
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


  const handleTestClick = async () => {
    try {
      if(!validate()){
        return;
      }
      const data = await submit(`${getApiURL()}/providers/test`);
      if (data && data.alerts) {
        console.log("Test successful");
        setTestResult("success");
        setAlertData(data.alerts);
      } else {
        setTestResult("error");
      }
    } catch (error) {
      setFormErrors({ error: error.toString() });
      console.error("Test failed:", error);
    }
  };

  const handleConnectClick = () => {
    if(!validate()){
      return;
    }
    onConnectChange(true, false);
    submit(`${getApiURL()}/providers/install`)
      .then((data) => {
        console.log("Connect Result:", data);
        onConnectChange(false, true);
        onAddProvider(data as Provider);
      })
      .catch((error) => {
        console.error("Connect failed:", error);
        const updatedFormErrors = { error: error.toString() };
        setFormErrors(updatedFormErrors);
        onFormChange(formValues, updatedFormErrors);
        onConnectChange(false, false);
    });

  };


  console.log("ProviderForm component loaded");
  return (
    <div>
      <form className={isConnected ? "connected-form" : ""}>
      <div className="form-group">
        <label htmlFor="provider_name" className="label-container">
          <span className="method-name">Provider Name:</span>
          <span className="question-icon">
            <FaQuestionCircle />
          </span>
        </label>
        <input
          type="text"
          id="provider_name"
          name="provider_name"
          value={formValues.provider_name || ""}
          onChange={handleInputChange}
          placeholder="Enter provider name"
          disabled={isConnected}
        />
      </div>
        {Object.keys(provider.config).map((configKey) => {
          const method = provider.config[configKey];
          const isHovered = hoveredLabel === configKey;
          return (
            <div className="form-group" key={configKey}>
              <label
                htmlFor={configKey}
                className="label-container"
                onMouseEnter={() => handleLabelMouseEnter(configKey)}
                onMouseLeave={() => handleLabelMouseLeave(configKey)}
              >
                <span className="method-name">
                  {method.description}
                  {method.required !== false ? "" : " (optional)"}:
                </span>
                <span className="question-icon">
                  { method.hint && <FaQuestionCircle /> }
                </span>
                {isHovered && method.hint && (
                  <div className="help-bubble-container">
                    <div className="help-bubble">
                      <span className="hint">{method.hint}</span>
                    </div>
                  </div>
                )}
              </label>
              <input
                type={method.type}
                id={configKey}
                name={configKey}
                value={formValues[configKey] || ""}
                onChange={handleInputChange}
                placeholder={method.placeholder || "Enter " + configKey}
              />
            </div>
          );
        })}
        {/* Hidden input for provider ID */}
        <input type="hidden" name="providerId" value={provider.id} />
        <div className="button-group">
          <button
            type="button"
            className="test-button"
            onClick={handleTestClick}
          >
            Test
          </button>
          <button
            type="button"
            className="connect-button"
            onClick={handleConnectClick}
          >
            Connect
          </button>
        </div>
      </form>
      {formErrors.error && (
        <div className="error-message">
          Error while testing the provider: &quot;{formErrors.error}&quot;
        </div>
      )}
      {testResult === "success" && (
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
                <tr key={alert.id || Math.random()}>
                  <Alert alert={alert} provider={formValues.provider_id} />
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
