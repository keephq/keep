import { useProviders } from "@/utils/hooks/useProviders";
import { getYamlWorkflowDefinitionSchema } from "./yaml.schema";
import { useMemo } from "react";
import { zodToJsonSchema } from "zod-to-json-schema";
import { YamlWorkflowDefinitionSchema } from "./yaml.schema";

export function useWorkflowJsonSchema() {
  const { data: { providers } = {} } = useProviders();
  return useMemo(() => {
    if (!providers) {
      return zodToJsonSchema(YamlWorkflowDefinitionSchema, "WorkflowSchema");
    }
    return zodToJsonSchema(
      getYamlWorkflowDefinitionSchema(providers),
      "WorkflowSchema"
    );
  }, [providers]);
}
