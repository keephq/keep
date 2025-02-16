import { Edge, Node } from "@xyflow/react";
import { Workflow } from "@/shared/api/workflows";
import { z } from "zod";

export type WorkflowMetadata = Pick<Workflow, "name" | "description">;

export type V2PropertiesCondition = {
  value: string;
  compare_to: string;
};

export type V2PropertiesStep = {
  stepParams: Record<string, any>;
};

export type V2PropertiesAction = {
  actionParams: Record<string, any>;
};

export type V2StepProperties =
  | V2PropertiesCondition
  | V2PropertiesStep
  | V2PropertiesAction;

export type V2Properties = Record<string, any>;

export type Definition = {
  sequence: V2Step[];
  properties: V2Properties;
  isValid?: boolean;
};

export type DefinitionV2 = {
  value: {
    sequence: V2Step[];
    properties: V2Properties;
  };
  isValid: boolean;
};

export const V2StepManualTriggerSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("trigger"),
  type: z.literal("manual"),
  properties: z.object({
    manual: z.literal("true"),
  }),
});

export const V2StepIntervalTriggerSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("trigger"),
  type: z.literal("interval"),
  properties: z.object({
    interval: z.string(),
  }),
});

export const V2StepAlertTriggerSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("trigger"),
  type: z.literal("alert"),
  properties: z.object({
    alert: z.record(z.string(), z.any()),
  }),
});

export const IncidentEventEnum = z.enum(["created", "updated", "deleted"]);

export const V2StepIncidentTriggerSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("trigger"),
  type: z.literal("incident"),
  properties: z.object({
    incident: z.object({
      events: z.array(IncidentEventEnum),
    }),
  }),
});

export const V2StepTriggerSchema = z.union([
  V2StepManualTriggerSchema,
  V2StepIntervalTriggerSchema,
  V2StepAlertTriggerSchema,
  V2StepIncidentTriggerSchema,
]);

export const V2ActionSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("task"),
  type: z.string().startsWith("action"),
  properties: z.object({
    actionParams: z.array(z.string()),
    config: z.string().optional(),
    with: z
      .record(z.string(), z.any())
      .superRefine((withObj, ctx) => {
        console.log(withObj, ctx);
        // const actionParams = ctx.path[0].properties.actionParams;
        // const withKeys = Object.keys(withObj);

        // // Check if all keys in 'with' are present in actionParams
        // const validKeys = withKeys.every((key) => actionParams.includes(key));

        // if (!validKeys) {
        //   ctx.addIssue({
        //     code: z.ZodIssueCode.custom,
        //     message: "All keys in 'with' must be listed in actionParams",
        //     path: ["with"],
        //   });
        // }
      })
      .optional(),
  }),
});

export type V2ActionStep = z.infer<typeof V2ActionSchema>;

export const V2StepStepSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("task"),
  type: z.string().startsWith("step"),
  properties: z.object({
    stepParams: z.array(z.string()),
    config: z.string().optional(),
    with: z
      .record(z.string(), z.any())
      .superRefine((withObj, ctx) => {
        console.log(withObj, ctx);
      })
      .optional(),
  }),
});

export type V2StepStep = z.infer<typeof V2StepStepSchema>;

export type V2StepTrigger = z.infer<typeof V2StepTriggerSchema>;

export const FlatV2StepSchema = z.union([
  V2StepTriggerSchema,
  V2ActionSchema,
  V2StepStepSchema,
]);

export type FlatV2Step = z.infer<typeof FlatV2StepSchema>;

export const V2StepConditionAssertSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("switch"),
  type: z.literal("condition-assert"),
  properties: z.object({
    value: z.string(),
    compare_to: z.string(),
  }),
  branches: z.object({
    true: z.array(FlatV2StepSchema),
    false: z.array(FlatV2StepSchema),
  }),
});

export type V2StepConditionAssert = z.infer<typeof V2StepConditionAssertSchema>;

export const V2StepConditionThresholdSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("switch"),
  type: z.literal("condition-threshold"),
  properties: z.object({
    value: z.string(),
    compare_to: z.string(),
  }),
  branches: z.object({
    true: z.array(FlatV2StepSchema),
    false: z.array(FlatV2StepSchema),
  }),
});

export type V2StepConditionThreshold = z.infer<
  typeof V2StepConditionThresholdSchema
>;

export const V2StepForeachSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("container"),
  type: z.literal("foreach"),
  properties: z.object({
    value: z.string(),
  }),
  sequence: z.array(FlatV2StepSchema),
});

export type V2StepForeach = z.infer<typeof V2StepForeachSchema>;

export const V2StepSchema = z.union([
  V2StepTriggerSchema,
  V2ActionSchema,
  V2StepStepSchema,
  V2StepConditionAssertSchema,
  V2StepConditionThresholdSchema,
  V2StepForeachSchema,
]);

export const V2StepTemplateSchema = z.union([
  V2StepTriggerSchema,
  V2ActionSchema.partial({ id: true }),
  V2StepStepSchema.partial({ id: true }),
  V2StepConditionAssertSchema.partial({ id: true }),
  V2StepConditionThresholdSchema.partial({ id: true }),
  V2StepForeachSchema.partial({ id: true }),
]);

export type V2StepTemplate = z.infer<typeof V2StepTemplateSchema>;

export const V2StartStepSchema = z.object({
  id: z.literal("start"),
  type: z.literal("start"),
  componentType: z.literal("start"),
  properties: z.object({}),
  name: z.literal("start"),
});

export type V2StartStep = z.infer<typeof V2StartStepSchema>;

export const V2EndStepSchema = z.object({
  id: z.literal("end"),
  type: z.literal("end"),
  componentType: z.literal("end"),
  properties: z.object({}),
  name: z.literal("end"),
});

export type V2EndStep = z.infer<typeof V2EndStepSchema>;

export type V2Step = z.infer<typeof V2StepSchema>;

// export type V2Step = {
//   id: string;
//   name?: string;
//   componentType: string;
//   type: string;
//   properties: V2StepProperties;
//   branches?: {
//     true: V2Step[];
//     false: V2Step[];
//   };
//   sequence?: V2Step[];
//   edgeNotNeeded?: boolean;
//   edgeLabel?: string;
//   edgeColor?: string;
//   edgeSource?: string;
//   edgeTarget?: string;
//   notClickable?: boolean;
// };

export type NodeData = Node["data"] & Record<string, any>;
export type NodeStepMeta = { id: string; label?: string };
export type FlowNode = Node & {
  prevStepId?: string | string[];
  edge_label?: string;
  data: NodeData;
  isDraggable?: boolean;
  nextStepId?: string | string[];
  prevStep?: NodeStepMeta[] | NodeStepMeta | null;
  nextStep?: NodeStepMeta[] | NodeStepMeta | null;
  prevNodeId?: string | null;
  nextNodeId?: string | null;
  id: string;
  isNested: boolean;
};

export type StoreGet = () => FlowState;
export type StoreSet = (
  state:
    | FlowState
    | Partial<FlowState>
    | ((state: FlowState) => FlowState | Partial<FlowState>)
) => void;

export interface FlowStateValues {
  workflowId: string | null;
  definition: DefinitionV2 | null;
  nodes: FlowNode[];
  edges: Edge[];
  selectedNode: string | null;
  selectedEdge: string | null;
  v2Properties: Record<string, any>;
  toolboxConfiguration: ToolboxConfiguration | null;
  isLayouted: boolean;
  isInitialized: boolean;

  // Lifecycle
  changes: number;
  synced: boolean;
  canDeploy: boolean;
  isSaving: boolean;
  isLoading: boolean;
  validationErrors: Record<string, string>;

  // UI
  editorOpen: boolean;
  saveRequestCount: number;
  runRequestCount: number;
}

export interface FlowState extends FlowStateValues {
  triggerSave: () => void;
  triggerRun: () => void;
  setIsSaving: (state: boolean) => void;
  setCanDeploy: (deploy: boolean) => void;
  setSynced: (sync: boolean) => void;
  setSelectedEdge: (id: string | null) => void;
  setIsLayouted: (isLayouted: boolean) => void;
  addNodeBetween: (
    nodeOrEdgeId: string,
    step: V2Step,
    type: "node" | "edge"
  ) => void;
  setToolBoxConfig: (config: ToolboxConfiguration) => void;
  setEditorOpen: (open: boolean) => void;
  updateSelectedNodeData: (key: string, value: any) => void;
  updateV2Properties: (properties: Record<string, any>) => void;
  setSelectedNode: (id: string | null) => void;
  onNodesChange: (changes: any) => void;
  onEdgesChange: (changes: any) => void;
  onConnect: (connection: any) => void;
  onDragOver: (event: React.DragEvent) => void;
  onDrop: (event: DragEvent, screenToFlowPosition: any) => void;
  setNodes: (nodes: FlowNode[]) => void;
  setEdges: (edges: Edge[]) => void;
  getNodeById: (id: string) => FlowNode | undefined;
  deleteNodes: (ids: string | string[]) => void;
  getNextEdge: (nodeId: string) => Edge | undefined;
  reset: () => void;
  setDefinition: (def: DefinitionV2) => void;
  setIsLoading: (loading: boolean) => void;
  onLayout: (params: {
    direction: string;
    useInitialNodes?: boolean;
    initialNodes?: FlowNode[];
    initialEdges?: Edge[];
  }) => void;
  initializeWorkflow: (
    workflowId: string | null,
    toolboxConfiguration: ToolboxConfiguration
  ) => void;
  updateDefinition: () => void;
}
export type ToolboxConfiguration = {
  groups: {
    name: string;
    steps: Omit<V2Step, "id">[];
  }[];
};
