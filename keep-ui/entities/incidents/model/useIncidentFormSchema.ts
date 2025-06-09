/**
 * Hook for managing incident form schemas
 */

import { useApiUrl } from "@/utils/hooks/useConfig";
import useSWR from "swr";
import { getApiURL } from "@/shared/lib/utils";

export interface FormFieldSchema {
  name: string;
  label: string;
  type: "text" | "textarea" | "select" | "checkbox" | "radio" | "number" | "date";
  description?: string;
  required: boolean;
  default_value?: any;
  
  // For select/radio fields
  options?: string[];
  
  // For text/textarea fields  
  placeholder?: string;
  max_length?: number;
  
  // For number fields
  min_value?: number;
  max_value?: number;
}

export interface IncidentFormSchema {
  tenant_id: string;
  name: string;
  description?: string;
  fields: FormFieldSchema[];
  is_active: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface IncidentFormSchemaDto {
  name: string;
  description?: string;
  fields: FormFieldSchema[];
  is_active: boolean;
}

/**
 * Hook to fetch the incident form schema for the current tenant
 */
export function useIncidentFormSchema() {
  const apiUrl = useApiUrl();
  
  const { data, error, mutate } = useSWR<IncidentFormSchema>(
    `${apiUrl}/incidents/form-schema`,
    (url: string) => fetch(url).then((res) => {
      if (res.status === 404) {
        return null; // No schema configured
      }
      if (!res.ok) {
        throw new Error(`Failed to fetch form schema: ${res.statusText}`);
      }
      return res.json();
    })
  );

  return {
    formSchema: data,
    isLoading: !error && !data,
    isError: error,
    mutate,
  };
}

/**
 * Hook to create or update incident form schema
 */
export function useIncidentFormSchemaActions() {
  const apiUrl = useApiUrl();
  
  const createOrUpdateSchema = async (schema: IncidentFormSchemaDto): Promise<IncidentFormSchema> => {
    const response = await fetch(`${apiUrl}/incidents/form-schema`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(schema),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to save form schema: ${response.statusText}`);
    }
    
    return response.json();
  };
  
  const deleteSchema = async (): Promise<void> => {
    const response = await fetch(`${apiUrl}/incidents/form-schema`, {
      method: "DELETE",
    });
    
    if (!response.ok) {
      throw new Error(`Failed to delete form schema: ${response.statusText}`);
    }
  };
  
  return {
    createOrUpdateSchema,
    deleteSchema,
  };
}