import { useMemo } from "react";
import { useProviders } from "@/utils/hooks/useProviders";
import {
  getYamlWorkflowDefinitionSchema,
  YamlWorkflowDefinitionSchema,
} from "../model/yaml.schema";

export function useWorkflowZodSchema() {
  const { data: { providers } = {} } = useProviders();
  return useMemo(() => {
    if (!providers) {
      return YamlWorkflowDefinitionSchema;
    }
    return getYamlWorkflowDefinitionSchema(providers);
  }, [providers]);
}
