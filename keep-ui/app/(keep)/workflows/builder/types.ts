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

export type FlowState = {
  nodes: FlowNode[];
  edges: Edge[];
  selectedNode: string | null;
  v2Properties: V2Properties;
  openGlobalEditor: boolean;
  stepEditorOpenForNode: string | null;
  toolboxConfiguration: Record<string, any>;
  onNodesChange: OnNodesChange<FlowNode>;
  onEdgesChange: OnEdgesChange<Edge>;
  onConnect: OnConnect;
  onDragOver: (event: React.DragEvent) => void;
  onDrop: (
    event: React.DragEvent,
    screenToFlowPosition: (coords: { x: number; y: number }) => {
      x: number;
      y: number;
    }
  ) => void;
  setNodes: (nodes: FlowNode[]) => void;
  setEdges: (edges: Edge[]) => void;
  getNodeById: (id: string | null) => FlowNode | undefined;
  deleteNodes: (ids: string | string[]) => void;
  setSelectedNode: (id: string | null) => void;
  setV2Properties: (properties: V2Properties) => void;
  setOpneGlobalEditor: (open: boolean) => void;
  updateSelectedNodeData: (key: string, value: any) => void;
  updateV2Properties: (properties: V2Properties) => void;
  setStepEditorOpenForNode: (nodeId: string | null) => void;
  setToolBoxConfig: (config: Record<string, any>) => void;
  addNodeBetween: (
    nodeOrEdge: string | null,
    step: V2Step,
    type: string
  ) => void;
  isLayouted: boolean;
  setIsLayouted: (isLayouted: boolean) => void;
  selectedEdge: string | null;
  setSelectedEdge: (id: string | null) => void;
  changes: number;
  setChanges: (changes: number) => void;
  firstInitilisationDone: boolean;
  setFirstInitilisationDone: (firstInitilisationDone: boolean) => void;
  setErrorNode: (id: string | null) => void;
  errorNode: string | null;
  synced: boolean;
  setSynced: (synced: boolean) => void;
  canDeploy: boolean;
  setCanDeploy: (deploy: boolean) => void;
  reset: () => void;
};

export type FlowStateValues = Pick<
  FlowState,
  | "nodes"
  | "edges"
  | "selectedNode"
  | "v2Properties"
  | "openGlobalEditor"
  | "stepEditorOpenForNode"
  | "toolboxConfiguration"
  | "isLayouted"
  | "selectedEdge"
  | "changes"
  | "firstInitilisationDone"
  | "errorNode"
  | "synced"
  | "canDeploy"
>;
