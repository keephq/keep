import { Edge, Node } from "@xyflow/react";
import { Workflow } from "@/shared/api/workflows";

export type WorkflowMetadata = Pick<Workflow, "name" | "description">;

export type V2PropertiesManualTrigger = {
  manual: "true";
};

export type V2PropertiesIntervalTrigger = {
  interval: string;
};

export type V2PropertiesAlertTrigger = {
  alert: {
    source: string;
  } & Record<string, any>;
};

export type V2PropertiesIncidentTrigger = {
  incident: {
    events: string[];
  };
};

export type V2PropertiesCondition = {
  value: string;
  compare_to: string;
};

export type V2PropertiesStep = {
  stepParams: string[];
};

export type V2PropertiesAction = {
  actionParams: string[];
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

export type V2StepTrigger = {
  id: string;
  name: string;
  componentType: "trigger";
  type: string;
  properties:
    | V2PropertiesManualTrigger
    | V2PropertiesIntervalTrigger
    | V2PropertiesAlertTrigger
    | V2PropertiesIncidentTrigger;
};

export type V2StepAction = {
  id: string;
  name: string;
  componentType: "action";
  type: string;
  properties: V2PropertiesAction;
};

export type V2StepSwitch = {
  id: string;
  name: string;
  componentType: "switch";
  type: string;
  properties: V2PropertiesCondition;
  branches: {
    true: V2Step[];
    false: V2Step[];
  };
};

export type V2StepForeach = {
  id: string;
  name: string;
  componentType: "foreach";
  type: string;
  properties: Record<string, any>;
  sequence: V2Step[];
};

export type V2Step =
  | V2StepTrigger
  | V2StepAction
  | V2StepSwitch
  | V2StepForeach;

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

  // Lifecycle
  changes: number;
  synced: boolean;
  canDeploy: boolean;
  isSaving: boolean;
  isLoading: boolean;
  validationErrors: Record<string, string>;

  // UI
  editorOpen: boolean;
  buttonsEnabled: boolean;
  saveRequestCount: number;
  runRequestCount: number;
}

export interface FlowState extends FlowStateValues {
  setButtonsEnabled: (state: boolean) => void;
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
    steps: Partial<V2Step>[];
  }[];
};
