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

  export type V2Properties = Record<string, any>;

  export type V2Step = {
    id: string;
    name?: string;
    componentType: string;
    type: string;
    properties?: V2Properties;
    branches?: {
      true?: V2Step[];
      false?: V2Step[];
    };
    sequence?: V2Step[] | V2Step;
  };

  export type NodeData = Node["data"] & Record<string, any>;
  export type FlowNode = Node & {
    prevStepId?: string;
    edge_label?: string;
    data: NodeData;
  };

  const initialNodes: FlowNode[] = [
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

  const initialEdges: Edge[] = [
    { id: "a->b", type: "custom-edge", source: "a", target: "b" },
    { id: "b->c", type: "custom-edge", source: "b", target: "c" },
  ];

  export type FlowState = {
    nodes: FlowNode[];
    edges: Edge[];
    selectedNode: FlowNode | null;
    v2Properties: V2Properties;
    openGlobalEditor: boolean;
    stepEditorOpenForNode: string | null;
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
    // addNode: (node: Partial<FlowNode>) => void;
    setSelectedNode: (node: FlowNode | null) => void;
    setV2Properties: (properties: V2Properties) => void;
    setOpneGlobalEditor: (open: boolean) => void;
    // updateNodeData: (nodeId: string, key: string, value: any) => void;
    updateSelectedNodeData: (key: string, value: any) => void;
    updateV2Properties: (key: string, value: any) => void;
    setStepEditorOpenForNode: (nodeId: string, open: boolean) => void;
    updateEdge: (id: string, key: string, value: any) => void;
  };

  const useStore = create<FlowState>((set, get) => ({
    nodes: initialNodes,
    edges: initialEdges,
    selectedNode: null,
    v2Properties: {},
    openGlobalEditor: true,
    stepEditorOpenForNode: null,
    setOpneGlobalEditor: (open) => set({ openGlobalEditor: open }),
    updateSelectedNodeData: (key, value) => {
      const currentSelectedNode = get().selectedNode;
      if (currentSelectedNode) {
        const updatedNodes = get().nodes.map((node) =>
          node.id === currentSelectedNode.id
            ? { ...node, data: { ...node.data, [key]: value } }
            : node
        );
        set({
          nodes: updatedNodes,
          selectedNode: {
            ...currentSelectedNode,
            data: { ...currentSelectedNode.data, [key]: value },
          },
        });
      }
    },
    setV2Properties: (properties) => set({ v2Properties: properties }),
    updateV2Properties: (key, value) => {
      const updatedProperties = { ...get().v2Properties, [key]: value };
      set({ v2Properties: updatedProperties });
    },
    setSelectedNode: (node) => {
      set({ selectedNode: node });
      set({ openGlobalEditor: false });
    },
    setStepEditorOpenForNode: (nodeId: string) => {
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
      const canConnect = (sourceNode: FlowNode | undefined, targetNode: FlowNode | undefined) => {
        if (!sourceNode || !targetNode) return false;
  
        const sourceType = sourceNode?.data?.componentType;
        const targetType = targetNode?.data?.componentType;
  
        // Restriction logic based on node types
        if (sourceType === 'switch') {
          return get().edges.filter(edge => edge.source === source).length < 2;
        }
        if (sourceType === 'foreach' || sourceNode?.data?.type==='foreach') {
          return true;
        }
        return get().edges.filter(edge => edge.source === source).length === 0;
      };
  
      // Check if the connection is allowed
      if (canConnect(sourceNode, targetNode)) {
        const edge = { ...connection, type: "custom-edge" };
        set({ edges: addEdge(edge, get().edges) });
      } else {
        console.warn('Connection not allowed based on node types');
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
        step = JSON.parse(step);
        if (!step) return;
        // Use the screenToFlowPosition function to get flow coordinates
        const position = screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        });
        const newUuid = uuidv4();
        const newNode: FlowNode = {
          id: newUuid,
          type: "custom",
          position, // Use the position object with x and y
          data: {
            label: step.name! as string,
            ...step,
            id: newUuid,
          },
        };

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
      set({ edges: get().edges.filter((edge) => !idArray.includes(edge.id)) });
    },
    deleteNodes: (ids) => {
      const idArray = Array.isArray(ids) ? ids : [ids];
      set({ nodes: get().nodes.filter((node) => !idArray.includes(node.id)) });
    },
    updateEdge: (id: string, key: string, value: any) => {
      const edge = get().edges.find((e) => e.id === id);
      if (!edge) return;
      const newEdge = { ...edge, [key]: value };
      set({ edges: get().edges.map((e) => (e.id === edge.id ? newEdge : e)) });
    },
    updateNode: (node) =>
      set({ nodes: get().nodes.map((n) => (n.id === node.id ? node : n)) }),
    duplicateNode: (node) => {
      const { data, position } = node;
      const newUuid = uuidv4();
      const newNode: FlowNode = {
        ...node,
        data: { ...data, id: newUuid },
        id: newUuid,
        position: { x: position.x + 100, y: position.y + 100 },
      };
      set({ nodes: [...get().nodes, newNode] });
    },
  }));

  export default useStore;
