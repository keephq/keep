import { create } from "zustand";
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

export type FlowNode = Node & {
  prevStepId?: string;
  edge_label?: string;
  data: Node["data"] & {
    id: string;
    type: string;
    componentType: string;
    name: string;
  };
};

const initialNodes = [
  {
    id: "a",
    position: { x: 0, y: 0 },
    data: { label: "Node A", type: "custom" },
    type: "custom",
  },
  {
    id: "b",
    position: { x: 0, y: 100 },
    data: { label: "Node B", type: "custom" },
    type: "custom",
  },
  {
    id: "c",
    position: { x: 0, y: 200 },
    data: { label: "Node C", type: "custom" },
    type: "custom",
  },
];

const initialEdges = [
  { id: "a->b", type: "custom-edge", source: "a", target: "b" },
  { id: "b->c", type: "custom-edge", source: "b", target: "c" },
];

export type FlowState = {
  nodes: FlowNode[];
  edges: Edge[];
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
  getNodeById: (id: string) => FlowNode | undefined;
  hasNode: (id: string) => boolean;
  deleteEdges: (ids: string | string[]) => void;
  deleteNodes: (ids: string | string[]) => void;
  updateNode: (node: FlowNode) => void;
  duplicateNode: (node: FlowNode) => void;
  addNode: (node: Partial<FlowNode>) => void; // Add this function
  createNode: (node: Partial<FlowNode>) => FlowNode;
};

const useStore = create<FlowState>((set, get) => ({
  nodes: initialNodes as FlowNode[],
  edges: initialEdges as Edge[],
  onNodesChange: (changes) =>
    set({ nodes: applyNodeChanges(changes, get().nodes) }),
  onEdgesChange: (changes) =>
    set({ edges: applyEdgeChanges(changes, get().edges) }),
  onConnect: (connection) => {
    const edge = { ...connection, type: "custom-edge" };
    set({ edges: addEdge(edge, get().edges) });
  },
  onDragOver: (event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  },
  // onDrop: (event, position) => {
  //   event.preventDefault();
  //   event.stopPropagation();

  //   const nodeType = event.dataTransfer.getData('application/reactflow');
  //   if (!nodeType) return;

  //   const newUuid = uuidv4();
  //   const newNode =  {
  //     id: newUuid,
  //     type: nodeType,
  //     position: { x: position.x, y: position.y }, // Ensure position is an object with x and y
  //     data: { label: `${nodeType} node`, type: nodeType, name: `${nodeType} node`, componentType: nodeType, id: newUuid },
  //   };
  //  set({ nodes: [...get().nodes, newNode] });
  // },
  onDrop: (event, screenToFlowPosition) => {
    event.preventDefault();
    event.stopPropagation();

    const nodeType = event.dataTransfer.getData("application/reactflow");

    console.log("nodeType=======>", nodeType)
    if (!nodeType) return;

    // Use the screenToFlowPosition function to get flow coordinates
    const position = screenToFlowPosition({
      x: event.clientX,
      y: event.clientY,
    });
    const newUuid = uuidv4();
    const newNode = {
      id: newUuid,
      type: nodeType,
      position, // Use the position object with x and y
      data: {
        label: `${nodeType} node`,
        type: nodeType,
        name: `${nodeType} node`,
        componentType: nodeType,
        id: newUuid,
      },
    };

    set({ nodes: [...get().nodes, newNode] });
  },
  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),
  hasNode: (id) => !!get().nodes.find((node) => node.id === id),
  getNodeById: (id) => get().nodes.find((node) => node.id === id),
  deleteEdges: (ids) => {
    const idArray = Array.isArray(ids) ? ids : [ids];
    set({ edges: get().edges.filter((edge) => !idArray.includes(edge.id)) });
  },
  deleteNodes: (ids) => {
    const idArray = Array.isArray(ids) ? ids : [ids];
    set({ nodes: get().nodes.filter((node) => !idArray.includes(node.id)) });
  },
  updateNode: (node) =>
    set({ nodes: get().nodes.map((n) => (n.id === node.id ? node : n)) }),
  duplicateNode: (node) => {
    const { data, position } = node;
    const newUuid = uuidv4();
    const newNode = {
      ...node,
      data: { ...data, id: newUuid },
      id: newUuid,
      position: { x: position.x + 100, y: position.y + 100 },
    };
    set({ nodes: [...get().nodes, newNode] });
  },
  addNode: (node: Partial<FlowNode>) => {
    const newUuid = uuidv4();
    // console.log("node in addNode", node);
    const newNode = {
      ...node,
      id: uuidv4(),
      type: "custom",
      data: {
        type: "custom",
        componentType: "custom",
        name: "custom",
        ...(node?.data ?? {}),
        id: newUuid,
      },
    };
    const newNodes = [...get().nodes, newNode];
    // console.log("newNodes in add Node", newNodes , newNode);
    set({
      nodes: newNodes,
    });
  },
  createNode: (node: Partial<FlowNode>) => {
    const newUuid = uuidv4();
    const newNode = {
      type: "custom",
      data: {
        type: "custom",
        componentType: "custom",
        name: "custom",
        ...(node?.data ?? {}),
        id: newUuid,
      },
      ...node,
      id: newUuid,
    };
    return newNode;
  },
}));

export default useStore;
