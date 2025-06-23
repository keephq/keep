import { z } from "zod";
import {
  WorkflowStrategySchema,
  YamlAssertConditionSchema,
  YamlStepOrActionSchema,
  YamlThresholdConditionSchema,
  YamlWorkflowDefinitionSchema,
} from "./yaml.schema";
import { WorkflowInputSchema } from "./schema";

export type YamlStepOrAction = z.infer<typeof YamlStepOrActionSchema>;
export type YamlThresholdCondition = z.infer<
  typeof YamlThresholdConditionSchema
>;

export type WorkflowInput = z.infer<typeof WorkflowInputSchema>;
export type WorkflowInputType = WorkflowInput["type"];

export type WorkflowStrategy = z.infer<typeof WorkflowStrategySchema>;

export type YamlAssertCondition = z.infer<typeof YamlAssertConditionSchema>;

export type YamlWorkflowDefinition = z.infer<
  typeof YamlWorkflowDefinitionSchema
>;
