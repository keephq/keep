import { useProviders } from "@/utils/hooks/useProviders";
import { getYamlWorkflowDefinitionSchema } from "../model/yaml.schema";
import { useMemo } from "react";
import { YamlWorkflowDefinitionSchema } from "../model/yaml.schema";
import { generateWorkflowYamlJsonSchema } from "./generateWorkflowYamlJsonSchema";

export function useWorkflowJsonSchema() {
  const { data: { providers } = {} } = useProviders();
  return useMemo(() => {
    if (!providers) {
      return generateWorkflowYamlJsonSchema(YamlWorkflowDefinitionSchema);
    }
    return generateWorkflowYamlJsonSchema(
      getYamlWorkflowDefinitionSchema(providers)
    );
  }, [providers]);
}
