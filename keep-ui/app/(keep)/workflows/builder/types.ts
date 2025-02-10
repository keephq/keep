import {
  Edge,
  Node,
  OnConnect,
  OnEdgesChange,
  OnNodesChange,
} from "@xyflow/react";

export type V2Properties = Record<string, any>;
export type Definition = {
  sequence: V2Step[];
  properties: V2Properties;
  isValid?: boolean;
};
export type ReactFlowDefinition = {
  value: {
    sequence: V2Step[];
    properties: V2Properties;
  };
  isValid?: boolean;
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
  triggerGenerate: number;
  triggerSave: number;
  triggerRun: number;
  isSaving: boolean;
}

export interface FlowState extends FlowStateValues {
  setCanDeploy: (deploy: boolean) => void;
  setSynced: (sync: boolean) => void;
  setErrorNode: (id: string | null) => void;
  setFirstInitilisationDone: (firstInitilisationDone: boolean) => void;
  setSelectedEdge: (id: string | null) => void;
  setChanges: (changes: number) => void;
  setIsLayouted: (isLayouted: boolean) => void;
  addNodeBetween: (nodeOrEdge: string | null, step: any, type: string) => void;
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
  onDragOver: (event: React.DragEvent<HTMLDivElement>) => void;
  onDrop: (
    event: React.DragEvent<HTMLDivElement>,
    screenToFlowPosition: any
  ) => void;
  setNodes: (nodes: FlowNode[]) => void;
  setEdges: (edges: Edge[]) => void;
  getNodeById: (id: string) => FlowNode | undefined;
  deleteNodes: (ids: string | string[]) => void;
  reset: () => void;
  setButtonsEnabled: (state: boolean) => void;
  setGenerateEnabled: (state: boolean) => void;
  setTriggerGenerate: () => void;
  setTriggerSave: () => void;
  setTriggerRun: () => void;
  setIsSaving: (state: boolean) => void;
}
