import { Edge, Node } from "@xyflow/react";
import { Workflow } from "@/shared/api/workflows";
import { z } from "zod";
import { Provider } from "@/app/(keep)/providers/providers";
export type WorkflowMetadata = Pick<Workflow, "name" | "description">;

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
    interval: z.union([z.string(), z.number()]),
  }),
});

export const V2StepAlertTriggerSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("trigger"),
  type: z.literal("alert"),
  properties: z.object({
    alert: z.record(z.string(), z.string()),
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

export type V2StepTrigger = z.infer<typeof V2StepTriggerSchema>;
export type TriggerType = V2StepTrigger["type"];

export const V2ActionSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("task"),
  type: z.string().startsWith("action"),
  properties: z.object({
    actionParams: z.array(z.string()),
    config: z.string().optional(),
    if: z.string().optional(),
    vars: z.record(z.string(), z.string()).optional(),
    with: z
      .record(
        z.string(),
        z.union([z.string(), z.number(), z.boolean(), z.object({})])
      )
      .superRefine((withObj, ctx) => {
        // console.log(withObj, { "ctx.path": ctx.path });
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
    vars: z.record(z.string(), z.string()).optional(),
    if: z.string().optional(),
    with: z
      .record(
        z.string(),
        z.union([z.string(), z.number(), z.boolean(), z.object({})])
      )
      .optional(),
  }),
});

export type V2StepStep = z.infer<typeof V2StepStepSchema>;

export const V2ActionOrStepSchema = z.union([V2ActionSchema, V2StepStepSchema]);

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
    true: z.array(V2ActionOrStepSchema),
    false: z.array(V2ActionOrStepSchema),
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
    true: z.array(V2ActionOrStepSchema),
    false: z.array(V2ActionOrStepSchema),
  }),
});

export type V2StepConditionThreshold = z.infer<
  typeof V2StepConditionThresholdSchema
>;

export const V2StepConditionSchema = z.union([
  V2StepConditionAssertSchema,
  V2StepConditionThresholdSchema,
]);

export type V2StepCondition = z.infer<typeof V2StepConditionSchema>;

export const V2StepForeachSchema = z.object({
  id: z.string(),
  name: z.string(),
  componentType: z.literal("container"),
  type: z.literal("foreach"),
  properties: z.object({
    value: z.string(),
  }),
  sequence: z.array(V2ActionOrStepSchema),
});

export type V2StepForeach = z.infer<typeof V2StepForeachSchema>;

export const V2StepSchema = z.union([
  V2ActionSchema,
  V2StepStepSchema,
  V2StepConditionAssertSchema,
  V2StepConditionThresholdSchema,
  V2StepForeachSchema,
]);

export const V2StepTemplateSchema = z.union([
  V2ActionSchema.partial({ id: true }),
  V2StepStepSchema.partial({ id: true }),
  V2StepConditionAssertSchema.partial({ id: true }),
  V2StepConditionThresholdSchema.partial({ id: true }),
  V2StepForeachSchema.partial({ id: true }),
]);

export type V2StepTemplate = z.infer<typeof V2StepTemplateSchema>;

export type V2StartStep = {
  id: "start";
  type: "start";
  componentType: "start";
  properties: Record<string, never>;
  name: "start";
};

export type V2EndStep = {
  id: "end";
  type: "end";
  componentType: "end";
  properties: Record<string, never>;
  name: "end";
};

export type TriggerStartLabelStep = {
  id: "trigger_start";
  name: "Triggers";
  type: "trigger";
  componentType: "trigger";
};

export type TriggerEndLabelStep = {
  id: "trigger_end";
  name: "Steps";
  type: "";
  componentType: "trigger";
  cantDelete: true;
  notClickable: true;
};

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

export type V2StepTempNode = V2Step & {
  type: "temp_node";
  componentType: "temp_node";
};

type UIProps = {
  edgeNotNeeded?: boolean;
  edgeLabel?: string;
  edgeColor?: string;
  edgeSource?: string;
  edgeTarget?: string | string[];
};

export type V2StepUI = V2Step & UIProps;

export type V2StepTriggerUI = V2StepTrigger & UIProps;

export type EmptyNode = {
  id: string;
  type: string;
  componentType: string;
  properties: Record<string, never>;
  name: string;
  isNested?: boolean;
};

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

export type ToolboxConfiguration = {
  groups: (
    | {
        name: "Triggers";
        steps: V2StepTrigger[];
      }
    | {
        name: string;
        steps: Omit<V2Step, "id">[];
      }
  )[];
};

export type ProvidersConfiguration = {
  providers: Provider[];
  installedProviders: Provider[];
};

export interface FlowStateValues {
  workflowId: string | null;
  definition: DefinitionV2 | null;
  nodes: FlowNode[];
  edges: Edge[];
  selectedNode: string | null;
  selectedEdge: string | null;
  v2Properties: Record<string, any>;
  toolboxConfiguration: ToolboxConfiguration | null;
  providers: Provider[] | null;
  installedProviders: Provider[] | null;
  isLayouted: boolean;
  isInitialized: boolean;

  // Lifecycle
  changes: number;
  isEditorSyncedWithNodes: boolean;
  canDeploy: boolean;
  isSaving: boolean;
  isLoading: boolean;
  validationErrors: Record<string, string>;

  lastChangedAt: number;
  lastDeployedAt: number;

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
  setEditorSynced: (sync: boolean) => void;
  setLastDeployedAt: (deployedAt: number) => void;
  setSelectedEdge: (id: string | null) => void;
  setIsLayouted: (isLayouted: boolean) => void;
  addNodeBetween: (
    nodeOrEdgeId: string,
    step: V2StepTemplate | V2StepTrigger,
    type: "node" | "edge"
  ) => string | null;
  addNodeBetweenSafe: (
    nodeOrEdgeId: string,
    step: V2StepTemplate | V2StepTrigger,
    type: "node" | "edge"
  ) => string | null;
  setProviders: (providers: Provider[]) => void;
  setInstalledProviders: (providers: Provider[]) => void;
  setEditorOpen: (open: boolean) => void;
  updateSelectedNodeData: (key: string, value: any) => void;
  updateV2Properties: (properties: Record<string, any>) => void;
  setSelectedNode: (id: string | null) => void;
  onNodesChange: (changes: any) => void;
  onEdgesChange: (changes: any) => void;
  setNodes: (nodes: FlowNode[]) => void;
  setEdges: (edges: Edge[]) => void;
  getNodeById: (id: string) => FlowNode | undefined;
  getEdgeById: (id: string) => Edge | undefined;
  deleteNodes: (ids: string | string[]) => string[];
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
    { providers, installedProviders }: ProvidersConfiguration
  ) => void;
  updateDefinition: () => void;
  // Deprecated
  onConnect: (connection: any) => void;
  onDragOver: (event: React.DragEvent) => void;
  onDrop: (event: DragEvent, screenToFlowPosition: any) => void;
}
