// @ts-nocheck
"use client";
import React, { useState } from "react";
import { useSession } from "../../utils/customAuth";
import { Provider } from "./provider-row";
import { getApiURL } from "../../utils/apiUrl";
import Alert from './alert';
import "./provider-form.css";

type ProviderFormProps = {
  provider: Provider;
  formData: Record<string, string>; // New prop for form data
  onFormChange: (formValues: Record<string, string>) => void;
};

const ProviderForm = ({
  provider,
  formData,
  onFormChange,
}: ProviderFormProps) => {
  console.log("Loading the ProviderForm component");
  const [formValues, setFormValues] = useState<{ [key: string]: string }>({
    provider_id: provider.id, // Include the provider ID in formValues
    ...formData,
  });
  const [formErrors, setFormErrors] = useState({});
  const [testResult, setTestResult] = useState("");
  const [connectResult, setConnectResult] = useState("");
  const [alertData, setAlertData] = useState([]);
  const [isConnected, setIsConnected] = useState(false);

  const { data: session, status, update } = useSession();
  // @ts-ignore
  if (!session?.accessToken) {
    console.log("No session access token, refreshing session from the server");
    update();
  }
  // update();
  // TODO - fix the typing here
  // @ts-ignore
  const accessToken = session?.accessToken;

  // @ts-ignore
  const validateForm = (updatedFormValues) => {
    const errors = {};
    for (const method of provider.authentication) {
      if (method.placeholder && !formValues[method.name] && method.required) {
        // @ts-ignore
        errors[method.name] = true;
      }
      // @ts-ignore
      if (
        "validation" in method &&
        formValues[method.name] &&
        !method.validation(updatedFormValues[method.name])
      ) {
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
  const validateAndSubmit = (requestUrl: string): Promise<any> => {
    return new Promise((resolve, reject) => {
      const errors = validateForm(formValues);
      if (Object.keys(errors).length === 0) {
        markErrors(errors);
        fetch(requestUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(formValues),
        })
          .then((response) => {
            if (response.ok) {
              return response.json();
            } else {
              throw new Error(response.statusText);
            }
          })
          .then((data) => {
            resolve(data);
            setFormErrors({});
          })
          .catch((error) => {
            reject(error);
            console.error("Error:", error);
          });
      } else {
        setFormErrors(errors);
        markErrors(errors);
        reject(new Error("Form validation failed"));
      }
    });
  };

  const handleTestClick = async () => {
    try {
      const data = await validateAndSubmit(
        `${getApiURL()}/providers/test`
      );
      if (data && data.alerts) {
        console.log("Test succeessful");
        setTestResult("success");
        setAlertData(data.alerts);
      } else {
        setTestResult("error");
      }
    } catch (error) {
      setFormErrors({"error": error.toString()})
      console.error("Test failed:", error);
    }
  };

  const handleConnectClick = () => {
    validateAndSubmit(`${getApiURL()}/providers/install`)
      .then((data) => {
        console.log("Connect Result:", data);
        setConnectResult(data.result);
        setIsConnected(true);
      })
      .catch((error) => {
        console.error("Connect failed:", error);
      });
  };
  console.log("ProviderForm component loaded");

  return (
    <div>
      <form className={isConnected ? "connected-form" : ""}>
        {provider.authentication.map((method) => (
          <div className="form-group" key={method.name}>
            <label htmlFor={method.name}>
              {method.desc}{method.required !== false ? "" : " (optional)"}:
            </label>
            <input
              type={method.type}
              id={method.name}
              name={method.name}
              value={formValues[method.name] || ""}
              onChange={handleInputChange}
              placeholder={method.placeholder}
              disabled={isConnected} // Disable the field when isConnected is true
            />
          </div>
        ))}
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
        <div className="error-message">Error while testing the provider: "{formErrors.error}"</div>
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
                <tr key={alert.id}>
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
