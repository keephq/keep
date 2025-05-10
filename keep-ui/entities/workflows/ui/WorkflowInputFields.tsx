import { Title } from "@tremor/react";
import { Select } from "@/shared/ui";

export interface WorkflowInput {
  name: string;
  type: string;
  description?: string;
  default?: any;
  required?: boolean;
  options?: string[];
  visuallyRequired?: boolean; // For inputs without defaults that aren't explicitly required
}

interface WorkflowInputFieldsProps {
  workflowInputs: WorkflowInput[];
  inputValues: Record<string, any>;
  onInputChange: (name: string, value: any) => void;
}

export function WorkflowInputFields({
  workflowInputs,
  inputValues,
  onInputChange,
}: WorkflowInputFieldsProps) {
  if (workflowInputs.length === 0) {
    return null;
  }

  // Render input fields based on input type
  const renderInputField = (input: WorkflowInput) => {
    const { name, type, description, required, visuallyRequired, options } =
      input;
    const value = inputValues[name] !== undefined ? inputValues[name] : "";
    const isEmpty = value === undefined || value === null || value === "";

    // Determine if this field is required for form submission
    const isEffectivelyRequired = required || input.default === undefined;

    // Visual indicator for required fields (either explicit or implicit)
    const requiredIndicator = (required || visuallyRequired) && (
      <span className="text-red-500">*</span>
    );

    // Error state for empty fields that need values
    const hasError = isEmpty && isEffectivelyRequired;

    switch (type?.toLowerCase()) {
      case "string":
        return (
          <div key={name} className="mb-4">
            <label className="block text-sm font-medium mb-1">
              {name} {requiredIndicator}
            </label>
            {description && (
              <p className="text-xs text-gray-500 mb-1">{description}</p>
            )}
            <input
              type="text"
              className={`w-full p-2 border rounded ${
                hasError ? "border-red-500" : "border-gray-300"
              }`}
              value={value}
              onChange={(e) => onInputChange(name, e.target.value)}
              required={isEffectivelyRequired}
            />
            {hasError && (
              <p className="text-xs text-red-500 mt-1">
                This field is required
              </p>
            )}
          </div>
        );

      case "number":
        return (
          <div key={name} className="mb-4">
            <label className="block text-sm font-medium mb-1">
              {name} {requiredIndicator}
            </label>
            {description && (
              <p className="text-xs text-gray-500 mb-1">{description}</p>
            )}
            <input
              type="number"
              className={`w-full p-2 border rounded ${
                hasError ? "border-red-500" : "border-gray-300"
              }`}
              value={value}
              onChange={(e) =>
                onInputChange(name, parseFloat(e.target.value) || 0)
              }
              required={isEffectivelyRequired}
            />
            {hasError && (
              <p className="text-xs text-red-500 mt-1">
                This field is required
              </p>
            )}
          </div>
        );

      case "boolean":
        return (
          <div key={name} className="mb-4">
            <div className="flex items-center">
              <input
                type="checkbox"
                className="mr-2"
                checked={!!value}
                onChange={(e) => onInputChange(name, e.target.checked)}
                id={`checkbox-${name}`}
              />
              <label
                htmlFor={`checkbox-${name}`}
                className="text-sm font-medium"
              >
                {name} {requiredIndicator}
              </label>
            </div>
            {description && (
              <p className="text-xs text-gray-500 mt-1">{description}</p>
            )}
            {/* Boolean fields don't typically show error states as they always have a value */}
          </div>
        );

      case "choice":
        return (
          <div key={name} className="mb-4">
            <label className="block text-sm font-medium mb-1">
              {name} {requiredIndicator}
            </label>
            {description && (
              <p className="text-xs text-gray-500 mb-1">{description}</p>
            )}
            <div className={hasError ? "border border-red-500 rounded" : ""}>
              <Select
                placeholder="Select an option"
                value={
                  value
                    ? { value: value.toString(), label: value.toString() }
                    : null
                }
                onChange={(option) =>
                  option && onInputChange(name, option.value)
                }
                options={options?.map((option) => ({
                  value: option,
                  label: option,
                }))}
                menuPlacement="bottom"
              />
            </div>
            {hasError && (
              <p className="text-xs text-red-500 mt-1">
                This field is required
              </p>
            )}
          </div>
        );

      default:
        return (
          <div key={name} className="mb-4">
            <label className="block text-sm font-medium mb-1">
              {name} {requiredIndicator}
            </label>
            {description && (
              <p className="text-xs text-gray-500 mb-1">{description}</p>
            )}
            <input
              type="text"
              className={`w-full p-2 border rounded ${
                hasError ? "border-red-500" : "border-gray-300"
              }`}
              value={value}
              onChange={(e) => onInputChange(name, e.target.value)}
              required={isEffectivelyRequired}
            />
            {hasError && (
              <p className="text-xs text-red-500 mt-1">
                This field is required
              </p>
            )}
          </div>
        );
    }
  };

  return workflowInputs.map(renderInputField);
}

export function areRequiredInputsFilled(
  workflowInputs: WorkflowInput[],
  inputValues: Record<string, any>
) {
  return workflowInputs.every((input) => {
    // Consider an input required if it doesn't have a default value
    const isEffectivelyRequired = input.required || input.default === undefined;

    if (isEffectivelyRequired) {
      const value = inputValues[input.name];
      // Check for empty values (undefined, null, empty string)
      const isEmpty = value === undefined || value === null || value === "";
      return !isEmpty;
    }
    return true;
  });
}
