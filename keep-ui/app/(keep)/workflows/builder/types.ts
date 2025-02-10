import { Edge, Node } from "@xyflow/react";

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

export type V2Step = {
  id: string;
  name?: string;
  componentType: string;
  type: string;
  properties: V2Properties;
  branches?: {
    true: V2Step[];
    false: V2Step[];
  };
  sequence?: V2Step[];
  edgeNotNeeded?: boolean;
  edgeLabel?: string;
  edgeColor?: string;
  edgeSource?: string;
  edgeTarget?: string;
  notClickable?: boolean;
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

export interface FlowStateValues {
  nodes: FlowNode[];
  edges: Edge[];
  selectedNode: string | null;
  v2Properties: Record<string, any>;
  openGlobalEditor: boolean;
  stepEditorOpenForNode: string | null;
  toolboxConfiguration: Record<string, any>;
  isLayouted: boolean;
  selectedEdge: string | null;
  changes: number;
  firstInitilisationDone: boolean;
  errorNode: string | null;
  synced: boolean;
  canDeploy: boolean;
  buttonsEnabled: boolean;
  generateEnabled: boolean;
  generateRequestCount: number;
  saveRequestCount: number;
  runRequestCount: number;
  isSaving: boolean;
  definition: DefinitionV2;
  isLoading: boolean;
  validationErrors: Set<[string, string | null]>;
}

export interface FlowState extends FlowStateValues {
  setButtonsEnabled: (state: boolean) => void;
  setGenerateEnabled: (state: boolean) => void;
  triggerGenerate: () => void;
  triggerSave: () => void;
  triggerRun: () => void;
  setIsSaving: (state: boolean) => void;
  setCanDeploy: (deploy: boolean) => void;
  setSynced: (sync: boolean) => void;
  setErrorNode: (id: string | null) => void;
  setFirstInitilisationDone: (firstInitilisationDone: boolean) => void;
  setSelectedEdge: (id: string | null) => void;
  setIsLayouted: (isLayouted: boolean) => void;
  addNodeBetween: (
    nodeOrEdge: string | null,
    step: V2Step,
    type: string
  ) => void;
  setToolBoxConfig: (config: Record<string, any>) => void;
  setOpneGlobalEditor: (open: boolean) => void;
  updateSelectedNodeData: (key: string, value: any) => void;
  setV2Properties: (properties: Record<string, any>) => void;
  updateV2Properties: (properties: Record<string, any>) => void;
  setSelectedNode: (id: string | null) => void;
  setStepEditorOpenForNode: (nodeId: string | null) => void;
  onNodesChange: (changes: any) => void;
  onEdgesChange: (changes: any) => void;
  onConnect: (connection: any) => void;
  onDragOver: (event: DragEvent) => void;
  onDrop: (event: DragEvent, screenToFlowPosition: any) => void;
  setNodes: (nodes: FlowNode[]) => void;
  setEdges: (edges: Edge[]) => void;
  getNodeById: (id: string) => FlowNode | undefined;
  deleteNodes: (ids: string | string[]) => void;
  reset: () => void;
  setDefinition: (def: DefinitionV2) => void;
  setIsLoading: (loading: boolean) => void;
  onLayout: (params: {
    direction: string;
    useInitialNodes?: boolean;
    initialNodes?: FlowNode[];
    initialEdges?: Edge[];
  }) => void;
  initializeWorkflow: (toolboxConfiguration: Record<string, any>) => void;
  updateDefinition: () => void;
}
