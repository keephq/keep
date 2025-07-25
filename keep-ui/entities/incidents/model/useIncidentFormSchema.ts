/**
 * Hook for managing incident form schemas
 */

import useSWR from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";

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
  id: string;
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
  schema_id?: string;
  name: string;
  description?: string;
  fields: FormFieldSchema[];
  is_active: boolean;
}

/**
 * Hook to fetch the incident form schema for the current tenant
 */
export function useIncidentFormSchema() {
  const api = useApi();
  
  const cacheKey = api.isReady() ? "/incidents/form-schema" : null;
  
  const { data, error, mutate } = useSWR<IncidentFormSchema | IncidentFormSchema[]>(
    cacheKey,
    () => api.get("/incidents/form-schema").then((response) => {
      // If response is an array, return the first active schema
      if (Array.isArray(response)) {
        return response.find(schema => schema.is_active) || null;
      }
      return response;
    }).catch((err) => {
      if (err.status === 404) {
        return null; // No schema configured
      }
      throw err;
    })
  );

  return {
    formSchema: Array.isArray(data) ? null : data,
    isLoading: !error && !data,
    isError: error,
    mutate,
  };
}

/**
 * Hook to create or update incident form schema
 */
export function useIncidentFormSchemaActions() {
  const api = useApi();
  
  const createOrUpdateSchema = async (schema: IncidentFormSchemaDto): Promise<IncidentFormSchema> => {
    return api.post("/incidents/form-schema", schema);
  };
  
  const deleteSchema = async (schemaId: string): Promise<void> => {
    return api.delete(`/incidents/form-schema?schema_id=${schemaId}`);
  };
  
  return {
    createOrUpdateSchema,
    deleteSchema,
  };
}