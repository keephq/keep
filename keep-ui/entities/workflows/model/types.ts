import { Edge, Node } from "@xyflow/react";
import { Workflow } from "@/shared/api/workflows";
import { z } from "zod";
import { Provider } from "@/shared/api/providers";
import {
  WorkflowPropertiesSchema,
  V2StepConditionSchema,
  V2StepSchema,
  V2StepConditionThresholdSchema,
  V2StepConditionAssertSchema,
  V2ActionOrStepSchema,
  V2ActionSchema,
  V2StepTriggerSchema,
  IncidentEventEnum,
  V2StepStepSchema,
  V2StepForeachSchema,
  V2StepTemplateSchema,
} from "./schema";
import { ValidationError } from "@/entities/workflows/lib/validation";

export type IncidentEvent = z.infer<typeof IncidentEventEnum>;
export type V2StepTrigger = z.infer<typeof V2StepTriggerSchema>;
export type TriggerType = V2StepTrigger["type"];
export type V2ActionStep = z.infer<typeof V2ActionSchema>;
export type V2StepStep = z.infer<typeof V2StepStepSchema>;
export type V2ActionOrStep = z.infer<typeof V2ActionOrStepSchema>;
export type V2StepConditionAssert = z.infer<typeof V2StepConditionAssertSchema>;
export type V2StepConditionThreshold = z.infer<
  typeof V2StepConditionThresholdSchema
>;
export type V2StepCondition = z.infer<typeof V2StepConditionSchema>;
export type V2StepForeach = z.infer<typeof V2StepForeachSchema>;
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
export type WorkflowMetadata = Pick<Workflow, "name" | "description">;
export type V2Properties = Record<string, any>;
export type WorkflowProperties = z.infer<typeof WorkflowPropertiesSchema>;

export type Definition = {
  sequence: V2Step[];
  properties: WorkflowProperties;
  isValid?: boolean;
};

export type DefinitionV2 = {
  value: {
    sequence: V2Step[];
    properties: WorkflowProperties;
  };
  isValid: boolean;
};

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
  notClickable?: boolean;
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

type ConditionAssertEndNodeData = {
  id: string;
  type: "condition-assert__end";
  componentType: "condition-assert__end";
  properties: Record<string, never>;
  name: string;
};

type ConditionThresholdEndNodeData = {
  id: string;
  type: "condition-threshold__end";
  componentType: "condition-threshold__end";
  properties: Record<string, never>;
  name: string;
};

// export type NodeData = Node["data"] & Record<string, any>;
export type NodeData = (
  | V2Step
  | V2StepTrigger
  | ConditionAssertEndNodeData
  | ConditionThresholdEndNodeData
) & {
  label?: string;
  islayouted?: boolean;
};

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

export type StoreGet = () => WorkflowState;
export type StoreSet = (
  state:
    | WorkflowState
    | Partial<WorkflowState>
    | ((state: WorkflowState) => WorkflowState | Partial<WorkflowState>)
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

export type InitializationConfiguration = {
  providers: Provider[];
  installedProviders: Provider[];
  secrets: Record<string, string>;
};

export interface WorkflowStateValues {
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
  secrets: Record<string, string> | null;
  isLayouted: boolean;
  isInitialized: boolean;

  // Lifecycle
  changes: number;
  isEditorSyncedWithNodes: boolean;
  canDeploy: boolean;
  isSaving: boolean;
  isLoading: boolean;
  isDeployed: boolean;
  validationErrors: Record<string, ValidationError>;

  lastChangedAt: number | null;
  lastDeployedAt: number | null;

  // UI
  editorOpen: boolean;
  saveRequestCount: number;

  yamlSchema: z.ZodSchema | null;
}

export interface WorkflowState extends WorkflowStateValues {
  triggerSave: () => void;
  setIsSaving: (state: boolean) => void;
  setCanDeploy: (deploy: boolean) => void;
  setEditorSynced: (sync: boolean) => void;
  setLastDeployedAt: (deployedAt: number) => void;
  setSelectedEdge: (id: string | null) => void;
  setIsLayouted: (isLayouted: boolean) => void;
  addNodeBetween: (
    nodeOrEdgeId: string,
    step: V2StepTrigger | Omit<V2Step, "id">,
    type: "node" | "edge"
  ) => string | null;
  addNodeBetweenSafe: (
    nodeOrEdgeId: string,
    step: V2StepTrigger | Omit<V2Step, "id">,
    type: "node" | "edge"
  ) => string | null;
  setProviders: (providers: Provider[]) => void;
  setInstalledProviders: (providers: Provider[]) => void;
  setSecrets: (secrets: Record<string, string>) => void;
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
    { providers, installedProviders, secrets }: InitializationConfiguration
  ) => void;
  updateDefinition: () => void;
  // Deprecated
  onConnect: (connection: any) => void;
  onDragOver: (event: React.DragEvent) => void;
  onDrop: (event: DragEvent, screenToFlowPosition: any) => void;
  updateFromYamlString: (yamlString: string) => void;
  validateDefinition: (definition: Definition) => {
    isValid: boolean;
    validationErrors: Record<string, ValidationError>;
    canDeploy: boolean;
  };
}
