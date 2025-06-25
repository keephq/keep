/**
 * Dynamic incident form component that renders custom fields based on tenant form schema
 */

import { useState, useEffect, useImperativeHandle, forwardRef } from "react";
import { Subtitle, Text } from "@tremor/react";
import { DynamicFormField } from "./DynamicFormField";
import { 
  useIncidentFormSchema, 
  FormFieldSchema 
} from "@/entities/incidents/model/useIncidentFormSchema";

interface DynamicIncidentFormProps {
  enrichments: Record<string, any>;
  onChange: (enrichments: Record<string, any>) => void;
  errors?: Record<string, string>;
  onValidationChange?: (hasErrors: boolean) => void;
}

export interface DynamicIncidentFormRef {
  getFieldErrors: () => Record<string, string>;
}

export const DynamicIncidentForm = forwardRef<DynamicIncidentFormRef, DynamicIncidentFormProps>((
  { enrichments, onChange, errors = {}, onValidationChange },
  ref
) => {
  const { formSchema, isLoading, isError } = useIncidentFormSchema();
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  
  // Expose validation errors for parent component through ref
  useImperativeHandle(ref, () => ({
    getFieldErrors: () => fieldErrors
  }), [fieldErrors]);

  // Validate fields on change and initial load
  useEffect(() => {
    if (!formSchema?.fields) return;

    const newErrors: Record<string, string> = {};
    
    formSchema.fields.forEach((field) => {
      const value = enrichments[field.name];
      
      // Check required fields
      if (field.required && (value === undefined || value === null || value === "")) {
        newErrors[field.name] = `${field.label} is required`;
        return;
      }

      // Type-specific validation
      if (value !== undefined && value !== null && value !== "") {
        switch (field.type) {
          case "text":
          case "textarea":
            if (typeof value !== "string") {
              newErrors[field.name] = `${field.label} must be text`;
            } else if (field.max_length && value.length > field.max_length) {
              newErrors[field.name] = `${field.label} must be ${field.max_length} characters or less`;
            }
            break;

          case "number":
            const numValue = Number(value);
            if (isNaN(numValue)) {
              newErrors[field.name] = `${field.label} must be a number`;
            } else {
              if (field.min_value !== undefined && numValue < field.min_value) {
                newErrors[field.name] = `${field.label} must be at least ${field.min_value}`;
              }
              if (field.max_value !== undefined && numValue > field.max_value) {
                newErrors[field.name] = `${field.label} must be at most ${field.max_value}`;
              }
            }
            break;

          case "select":
          case "radio":
            if (field.options && !field.options.includes(value)) {
              newErrors[field.name] = `${field.label} must be one of: ${field.options.join(", ")}`;
            }
            break;

          case "checkbox":
            if (typeof value !== "boolean") {
              newErrors[field.name] = `${field.label} must be true or false`;
            }
            break;
        }
      }
    });

    setFieldErrors(newErrors);
    
    // Notify parent about validation state
    if (onValidationChange) {
      onValidationChange(Object.keys(newErrors).length > 0);
    }
  }, [enrichments, formSchema?.fields, onValidationChange]);

  const handleFieldChange = (fieldName: string, value: any) => {
    onChange({
      ...enrichments,
      [fieldName]: value,
    });
  };

  // Notify parent when no schema exists or is inactive
  useEffect(() => {
    if (onValidationChange) {
      const shouldRender = !isLoading && !isError && formSchema && formSchema.fields && formSchema.fields.length > 0 && formSchema.is_active;
      if (!shouldRender) {
        onValidationChange(false); // No validation errors when no schema
      }
    }
  }, [isLoading, isError, formSchema, onValidationChange]);

  // Don't render anything while loading
  if (isLoading) {
    return null;
  }

  // Don't render anything if there was an error (including 404)
  if (isError) {
    return null;
  }

  // Don't render if no schema or no fields
  if (!formSchema || !formSchema.fields || formSchema.fields.length === 0) {
    return null;
  }

  // Don't render if schema is not active
  if (!formSchema.is_active) {
    return null;
  }

  return (
    <div className="mt-4">
      <Subtitle>Additional Information</Subtitle>
      <Text className="text-gray-500 text-sm mt-1">
        {formSchema.description || "Please provide additional details for this incident"}
      </Text>
      
      {formSchema.fields.map((field: FormFieldSchema) => (
        <DynamicFormField
          key={field.name}
          field={field}
          value={enrichments[field.name]}
          onChange={(value) => handleFieldChange(field.name, value)}
          error={fieldErrors[field.name] || errors[field.name]}
        />
      ))}
    </div>
  );
});

DynamicIncidentForm.displayName = "DynamicIncidentForm";