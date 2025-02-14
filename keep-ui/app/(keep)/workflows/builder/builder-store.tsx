import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { v4 as uuidv4 } from "uuid";
import {
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  OnNodesChange,
  OnEdgesChange,
  OnConnect,
  Edge,
  Node,
} from "@xyflow/react";

import { createCustomEdgeMeta, processWorkflowV2 } from "utils/reactFlow";
import { createDefaultNodeV2 } from "../../../../utils/reactFlow";
import { ToolboxConfiguration } from "./types";

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

export type FlowState = {
  nodes: FlowNode[];
  edges: Edge[];
  selectedNode: string | null;
  v2Properties: V2Properties;
  openGlobalEditor: boolean;
  stepEditorOpenForNode: string | null;
  toolboxConfiguration: ToolboxConfiguration;
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
  hasNode: (id: string) => boolean;
  deleteEdges: (ids: string | string[]) => void;
  deleteNodes: (ids: string | string[]) => void;
  updateNode: (node: FlowNode) => void;
  duplicateNode: (node: FlowNode) => void;
  // addNode: (node: Partial<FlowNode>) => void;
  setSelectedNode: (id: string | null) => void;
  setV2Properties: (properties: V2Properties) => void;
  setOpneGlobalEditor: (open: boolean) => void;
  // updateNodeData: (nodeId: string, key: string, value: any) => void;
  updateSelectedNodeData: (key: string, value: any) => void;
  updateV2Properties: (properties: V2Properties) => void;
  setStepEditorOpenForNode: (nodeId: string | null) => void;
  updateEdge: (id: string, key: string, value: any) => void;
  setToolBoxConfig: (config: ToolboxConfiguration) => void;
  addNodeBetween: (
    nodeOrEdge: string | null,
    step: V2Step,
    type: string
  ) => void;
  isLayouted: boolean;
  setIsLayouted: (isLayouted: boolean) => void;
  selectedEdge: string | null;
  setSelectedEdge: (id: string | null) => void;
  getEdgeById: (id: string) => Edge | undefined;
  changes: number;
  setChanges: (changes: number) => void;
  firstInitilisationDone: boolean;
  setFirstInitilisationDone: (firstInitilisationDone: boolean) => void;
  lastSavedChanges: { nodes: FlowNode[] | null; edges: Edge[] | null };
  setLastSavedChanges: ({
    nodes,
    edges,
  }: {
    nodes: FlowNode[];
    edges: Edge[];
  }) => void;
  setErrorNode: (id: string | null) => void;
  errorNode: string | null;
  synced: boolean;
  setSynced: (synced: boolean) => void;
  canDeploy: boolean;
  setCanDeploy: (deploy: boolean) => void;
  getNextEdge: (nodeId: string) => Edge | null;
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
  | "lastSavedChanges"
  | "errorNode"
  | "synced"
  | "canDeploy"
>;

export type StoreGet = () => FlowState;
export type StoreSet = (
  state:
    | FlowState
    | Partial<FlowState>
    | ((state: FlowState) => FlowState | Partial<FlowState>)
) => void;

class WorkflowBuilderError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "WorkflowBuilderError";
  }
}

function addNodeBetween(
  nodeOrEdge: string | null,
  step: V2Step,
  type: string,
  set: StoreSet,
  get: StoreGet
) {
  if (!nodeOrEdge || !step) return;
  let edge = {} as Edge;
  if (type === "node") {
    edge = get().edges.find((edge) => edge.target === nodeOrEdge) as Edge;
  }

  if (type === "edge") {
    edge = get().edges.find((edge) => edge.id === nodeOrEdge) as Edge;
  }

  let { source: sourceId, target: targetId } = edge || {};
  if (!sourceId || !targetId) return;

  const isTriggerComponent = step.componentType === "trigger";

  if (sourceId !== "trigger_start" && isTriggerComponent) {
    return;
  }

  if (sourceId == "trigger_start" && !isTriggerComponent) {
    return;
  }

  const nodes = get().nodes;
  if (
    sourceId === "trigger_start" &&
    isTriggerComponent &&
    nodes.find((node) => node && step.id === node.id)
  ) {
    return;
  }

  let targetIndex = nodes.findIndex((node) => node.id === targetId);
  const sourceIndex = nodes.findIndex((node) => node.id === sourceId);
  if (targetIndex == -1) {
    return;
  }

  if (sourceId === "trigger_start") {
    targetId = "trigger_end";
  }
  const newNodeId = isTriggerComponent ? step.id : uuidv4();
  const cloneStep = JSON.parse(JSON.stringify(step));
  const newStep = { ...cloneStep, id: newNodeId };
  const edges = get().edges;

  let { nodes: newNodes, edges: newEdges } = processWorkflowV2(
    [
      {
        id: sourceId,
        type: "temp_node",
        name: "temp_node",
        componentType: "temp_node",
        edgeLabel: edge.label,
        edgeColor: edge?.style?.stroke,
      },
      newStep,
      {
        id: targetId,
        type: "temp_node",
        name: "temp_node",
        componentType: "temp_node",
        edgeNotNeeded: true,
      },
    ] as V2Step[],
    { x: 0, y: 0 },
    true
  );

  const finalEdges = [
    ...newEdges,
    ...(edges.filter(
      (edge) => !(edge.source == sourceId && edge.target == targetId)
    ) || []),
  ];

  const isNested = !!(
    nodes[targetIndex]?.isNested || nodes[sourceIndex]?.isNested
  );
  newNodes = newNodes.map((node) => ({ ...node, isNested }));
  newNodes = [
    ...nodes.slice(0, targetIndex),
    ...newNodes,
    ...nodes.slice(targetIndex),
  ];
  set({
    edges: finalEdges,
    nodes: newNodes,
    isLayouted: false,
    changes: get().changes + 1,
  });
  if (type == "edge") {
    set({
      selectedEdge: edges[edges.length - 1]?.id,
    });
  }

  if (type === "node") {
    set({ selectedNode: nodeOrEdge });
  } else if (newNodeId) {
    set({ selectedNode: newNodeId });
  }

  // debugger;
  switch (newNodeId) {
    case "interval":
    case "manual": {
      set({ v2Properties: { ...get().v2Properties, [newNodeId]: "" } });
      break;
    }
    case "alert": {
      set({
        v2Properties: {
          ...get().v2Properties,
          [newNodeId]: {},
        },
      });
      const updatedProperties = { ...get().v2Properties, ...step.properties };
      set({
        v2Properties: updatedProperties,
        changes: get().changes + 1,
        canDeploy: false,
      });
      break;
    }
    case "incident": {
      set({
        v2Properties: {
          ...get().v2Properties,
          [newNodeId]: {},
        },
      });
      break;
    }
  }
}

const defaultState: FlowStateValues = {
  nodes: [],
  edges: [],
  selectedNode: null,
  v2Properties: {},
  openGlobalEditor: true,
  stepEditorOpenForNode: null,
  toolboxConfiguration: {
    groups: [],
  } as ToolboxConfiguration,
  isLayouted: false,
  selectedEdge: null,
  changes: 0,
  lastSavedChanges: { nodes: [], edges: [] },
  firstInitilisationDone: false,
  errorNode: null,
  synced: true,
  canDeploy: false,
};

export const useStore = create<FlowState>()(
  devtools((set, get) => ({
    ...defaultState,
    setCanDeploy: (deploy) => set({ canDeploy: deploy }),
    setSynced: (sync) => set({ synced: sync }),
    setErrorNode: (id) => set({ errorNode: id }),
    setFirstInitilisationDone: (firstInitilisationDone) =>
      set({ firstInitilisationDone }),
    setLastSavedChanges: ({
      nodes,
      edges,
    }: {
      nodes: FlowNode[];
      edges: Edge[];
    }) => set({ lastSavedChanges: { nodes, edges } }),
    setSelectedEdge: (id) =>
      set({ selectedEdge: id, selectedNode: null, openGlobalEditor: true }),
    setChanges: (changes: number) => set({ changes: changes }),
    setIsLayouted: (isLayouted) => set({ isLayouted }),
    getEdgeById: (id) => get().edges.find((edge) => edge.id === id),
    addNodeBetween: (nodeOrEdge: string | null, step: any, type: string) => {
      addNodeBetween(nodeOrEdge, step, type, set, get);
    },
    setToolBoxConfig: (config) => set({ toolboxConfiguration: config }),
    setOpneGlobalEditor: (open) => set({ openGlobalEditor: open }),
    updateSelectedNodeData: (key, value) => {
      const currentSelectedNode = get().selectedNode;
      if (currentSelectedNode) {
        const updatedNodes = get().nodes.map((node) => {
          if (node.id === currentSelectedNode) {
            //properties changes  should not reconstructed the defintion. only recontrreconstructing if there are any structural changes are done on the flow.
            if (value) {
              node.data[key] = value;
            }
            if (!value) {
              delete node.data[key];
            }
            return { ...node };
          }
          return node;
        });
        set({
          nodes: updatedNodes,
          changes: get().changes + 1,
        });
      }
    },
    setV2Properties: (properties) =>
      set({ v2Properties: properties, canDeploy: false }),
    updateV2Properties: (properties) => {
      const updatedProperties = { ...get().v2Properties, ...properties };
      set({
        v2Properties: updatedProperties,
        changes: get().changes + 1,
        canDeploy: false,
      });
    },
    setSelectedNode: (id) => {
      set({
        selectedNode: id || null,
        openGlobalEditor: false,
        selectedEdge: null,
      });
    },
    setStepEditorOpenForNode: (nodeId) => {
      set({ openGlobalEditor: false });
      set({ stepEditorOpenForNode: nodeId });
    },
    onNodesChange: (changes) =>
      set({ nodes: applyNodeChanges(changes, get().nodes) }),
    onEdgesChange: (changes) =>
      set({ edges: applyEdgeChanges(changes, get().edges) }),
    onConnect: (connection) => {
      const { source, target } = connection;
      const sourceNode = get().getNodeById(source);
      const targetNode = get().getNodeById(target);

      // Define the connection restrictions
      const canConnect = (
        sourceNode: FlowNode | undefined,
        targetNode: FlowNode | undefined
      ) => {
        if (!sourceNode || !targetNode) return false;

        const sourceType = sourceNode?.data?.componentType;
        const targetType = targetNode?.data?.componentType;

        // Restriction logic based on node types
        if (sourceType === "switch") {
          return (
            get().edges.filter((edge) => edge.source === source).length < 2
          );
        }
        if (sourceType === "foreach" || sourceNode?.data?.type === "foreach") {
          return true;
        }
        return (
          get().edges.filter((edge) => edge.source === source).length === 0
        );
      };

      // Check if the connection is allowed
      if (canConnect(sourceNode, targetNode)) {
        const edge = { ...connection, type: "custom-edge" };
        set({ edges: addEdge(edge, get().edges) });
        set({
          nodes: get().nodes.map((node) => {
            if (node.id === target) {
              return { ...node, prevStepId: source, isDraggable: false };
            }
            if (node.id === source) {
              return { ...node, isDraggable: false };
            }
            return node;
          }),
        });
      } else {
        console.warn("Connection not allowed based on node types");
      }
    },

    onDragOver: (event) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
    },
    onDrop: (event, screenToFlowPosition) => {
      event.preventDefault();
      event.stopPropagation();

      try {
        let step: any = event.dataTransfer.getData("application/reactflow");
        if (!step) {
          return;
        }
        step = JSON.parse(step);
        if (!step) return;
        // Use the screenToFlowPosition function to get flow coordinates
        const position = screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        });
        const newUuid = uuidv4();
        const newNode = {
          id: newUuid,
          type: "custom",
          position, // Use the position object with x and y
          data: {
            label: step.name! as string,
            ...step,
            id: newUuid,
            name: step.name,
            type: step.type,
            componentType: step.componentType,
          },
          isDraggable: true,
          dragHandle: ".custom-drag-handle",
        } as FlowNode;

        set({ nodes: [...get().nodes, newNode] });
      } catch (err) {
        console.error(err);
      }
    },
    setNodes: (nodes) => set({ nodes }),
    setEdges: (edges) => set({ edges }),
    hasNode: (id) => !!get().nodes.find((node) => node.id === id),
    getNodeById: (id) => get().nodes.find((node) => node.id === id),
    deleteEdges: (ids) => {
      const idArray = Array.isArray(ids) ? ids : [ids];
      set({
        edges: get().edges.filter((edge) => !idArray.includes(edge.id)),
      });
    },
    deleteNodes: (ids) => {
      //for now handling only single node deletion. can later enhance to multiple deletions
      if (typeof ids !== "string") {
        return;
      }
      const nodes = get().nodes;
      const nodeStartIndex = nodes.findIndex((node) => ids == node.id);
      if (nodeStartIndex === -1) {
        return;
      }
      let idArray = Array.isArray(ids) ? ids : [ids];

      const startNode = nodes[nodeStartIndex];
      const customIdentifier = `${startNode?.data?.type}__end__${startNode?.id}`;

      let endIndex = nodes.findIndex((node) => node.id === customIdentifier);
      endIndex = endIndex === -1 ? nodeStartIndex : endIndex;

      const endNode = nodes[endIndex];

      let edges = get().edges;
      let finalEdges = edges;
      idArray = nodes
        .slice(nodeStartIndex, endIndex + 1)
        .map((node) => node.id);

      finalEdges = edges.filter(
        (edge) =>
          !(idArray.includes(edge.source) || idArray.includes(edge.target))
      );
      if (
        ["interval", "alert", "manual", "incident"].includes(ids) &&
        edges.some(
          (edge) => edge.source === "trigger_start" && edge.target !== ids
        )
      ) {
        edges = edges.filter((edge) => !idArray.includes(edge.source));
      }
      const sources = [
        ...new Set(edges.filter((edge) => startNode.id === edge.target)),
      ];
      const targets = [
        ...new Set(edges.filter((edge) => endNode.id === edge.source)),
      ];
      targets.forEach((edge) => {
        const target =
          edge.source === "trigger_start" ? "triggger_end" : edge.target;

        finalEdges = [
          ...finalEdges,
          ...sources
            .map((source: Edge) =>
              createCustomEdgeMeta(
                source.source,
                target,
                source.label as string
              )
            )
            .flat(1),
        ];
      });
      // }

      nodes[endIndex + 1].position = { x: 0, y: 0 };

      const newNode = createDefaultNodeV2(
        { ...nodes[endIndex + 1].data, islayouted: false },
        nodes[endIndex + 1].id
      );

      const newNodes = [
        ...nodes.slice(0, nodeStartIndex),
        newNode,
        ...nodes.slice(endIndex + 2),
      ];
      if (["manual", "alert", "interval", "incident"].includes(ids)) {
        const v2Properties = get().v2Properties;
        delete v2Properties[ids];
        set({ v2Properties });
      }
      set({
        edges: finalEdges,
        nodes: newNodes,
        selectedNode: null,
        isLayouted: false,
        changes: get().changes + 1,
        openGlobalEditor: true,
      });
    },
    updateEdge: (id: string, key: string, value: any) => {
      const edge = get().edges.find((e) => e.id === id);
      if (!edge) return;
      const newEdge = { ...edge, [key]: value };
      set({
        edges: get().edges.map((e) => (e.id === edge.id ? newEdge : e)),
      });
    },
    updateNode: (node) =>
      set({ nodes: get().nodes.map((n) => (n.id === node.id ? node : n)) }),
    duplicateNode: (node) => {
      const { data, position } = node;
      const newUuid = uuidv4();
      const newNode: FlowNode = {
        ...node,
        data: {
          ...data,
          id: newUuid,
        },
        isDraggable: true,
        id: newUuid,
        position: { x: position.x + 100, y: position.y + 100 },
        dragHandle: ".custom-drag-handle",
      };
      set({ nodes: [...get().nodes, newNode] });
    },
    getNextEdge: (nodeId: string) => {
      const node = get().getNodeById(nodeId);
      if (!node) {
        throw new WorkflowBuilderError("getNextEdge::Node not found");
      }
      const edge = get().edges.find((e) => e.source === nodeId);
      if (!edge) {
        throw new WorkflowBuilderError("getNextEdge::Edge not found");
      }
      return edge;
    },
    reset: () => set(defaultState),
  }))
);
