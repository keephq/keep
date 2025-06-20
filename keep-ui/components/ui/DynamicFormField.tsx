/**
 * Dynamic form field component that renders different input types based on schema
 * 
 * TODO: Add comprehensive input validation and XSS prevention
 * This will be addressed in a future security enhancement ticket
 * that will provide app-wide security utilities and patterns
 */

import { 
  TextInput, 
  Textarea, 
  Select, 
  SelectItem, 
  Switch,
  Text,
} from "@tremor/react";
import { FormFieldSchema } from "@/entities/incidents/model/useIncidentFormSchema";

interface DynamicFormFieldProps {
  field: FormFieldSchema;
  value: any;
  onChange: (value: any) => void;
  error?: string;
}

export function DynamicFormField({ 
  field, 
  value, 
  onChange, 
  error 
}: DynamicFormFieldProps) {
  const renderField = () => {
    const currentValue = value !== undefined ? value : field.default_value;

    switch (field.type) {
      case "text":
        return (
          <TextInput
            placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}`}
            value={currentValue || ""}
            onValueChange={onChange}
            error={!!error}
            errorMessage={error}
            maxLength={field.max_length}
          />
        );

      case "textarea":
        return (
          <Textarea
            placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}`}
            value={currentValue || ""}
            onValueChange={onChange}
            rows={3}
            maxLength={field.max_length}
            className={error ? "border-red-500" : ""}
          />
        );

      case "select":
        return (
          <Select
            placeholder={`Select ${field.label.toLowerCase()}`}
            value={currentValue || ""}
            onValueChange={onChange}
          >
            {field.options?.map((option) => (
              <SelectItem key={option} value={option}>
                {option}
              </SelectItem>
            ))}
          </Select>
        );

      case "radio":
        return (
          <div className="space-y-2">
            {field.options?.map((option) => (
              <label key={option} className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="radio"
                  name={field.name}
                  value={option}
                  checked={currentValue === option}
                  onChange={(e) => onChange(e.target.value)}
                  className="text-orange-500 focus:ring-orange-500"
                />
                <Text className="text-sm">{option}</Text>
              </label>
            ))}
          </div>
        );

      case "checkbox":
        return (
          <div className="flex items-center space-x-2">
            <Switch
              id={field.name}
              checked={currentValue || false}
              onChange={onChange}
              color="orange"
            />
            <Text className="text-sm">
              {field.description || field.label}
            </Text>
          </div>
        );

      case "number":
        return (
          <TextInput
            type="number"
            placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}`}
            value={currentValue?.toString() || ""}
            onValueChange={(stringValue) => {
              const numValue = stringValue === "" ? undefined : Number(stringValue);
              onChange(numValue);
            }}
            error={!!error}
            errorMessage={error}
            min={field.min_value}
            max={field.max_value}
          />
        );

      case "date":
        return (
          <TextInput
            type="date"
            value={currentValue || ""}
            onValueChange={onChange}
            error={!!error}
            errorMessage={error}
          />
        );

      default:
        return (
          <Text className="text-red-500">
            Unsupported field type: {field.type}
          </Text>
        );
    }
  };

  return (
    <div className="mt-2.5">
      <Text className="mb-2">
        {field.label}
        {field.required && (
          <span className="text-red-500 text-xs ml-1">*</span>
        )}
      </Text>
      {renderField()}
      {error && field.type !== "text" && field.type !== "number" && field.type !== "date" && (
        <Text className="text-red-500 text-xs mt-1">{error}</Text>
      )}
      {field.description && field.type !== "checkbox" && (
        <Text className="text-gray-500 text-xs mt-1">{field.description}</Text>
      )}
    </div>
  );
}