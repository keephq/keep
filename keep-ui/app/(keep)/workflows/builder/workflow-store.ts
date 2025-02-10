import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  Edge,
} from "@xyflow/react";
import { create } from "zustand";
import { devtools } from "zustand/middleware";
import {
  Definition,
  ValidatorConfigurationV2,
  ToolboxConfiguration,
} from "./types";
import { V2Properties, V2Step, FlowNode } from "./builder-store";
import {
  DefinitionV2,
  getDefinitionFromNodesEdgesProperties,
  getToolboxConfiguration,
} from "./utils";
import {
  createCustomEdgeMeta,
  createDefaultNodeV2,
  getTriggerSteps,
  processWorkflowV2,
} from "utils/reactFlow";
import { v4 as uuidv4 } from "uuid";
import { stepValidatorV2, globalValidatorV2 } from "./builder-validators";
import { parseWorkflow, generateWorkflow } from "./utils";
import { wrapDefinitionV2 } from "./utils";
import { YAMLException } from "js-yaml";
import { Provider } from "../../providers/providers";
import dagre, { graphlib } from "@dagrejs/dagre";

interface WorkflowStore {
  workflowId: string;
  // Core Flow State (from FlowState)
  nodes: FlowNode[];
  edges: Edge[];
  v2Properties: V2Properties;
  definition: DefinitionV2;
  changes: number;

  // UI State (from FlowState)
  selectedNode: string | null;
  selectedEdge: string | null;
  errorNodes: string[];
  openGlobalEditor: boolean;
  stepEditorOpenForNode: string | null;
  toolboxConfiguration: ToolboxConfiguration;
  isLayouted: boolean;
  isSaving: boolean;

  // Sync State (from FlowState + new)
  isPendingSync: boolean;
  lastSyncedAt: number;
  canDeploy: boolean;

  // Flow Actions
  updateNodes: (nodes: FlowNode[]) => void;
  updateEdges: (edges: Edge[]) => void;
  updateV2Properties: (properties: V2Properties) => Promise<void>;
  getNodeById: (id: string | null) => FlowNode | undefined;
  getEdgeById: (id: string) => Edge | undefined;
  getNextEdge: (nodeId: string) => Edge | null;

  // Node/Edge Management
  deleteNodes: (ids: string | string[]) => void;
  deleteEdges: (ids: string | string[]) => void;
  updateNode: (node: FlowNode) => void;
  updateEdge: (id: string, key: string, value: any) => void;
  duplicateNode: (node: FlowNode) => void;
  addNodeBetween: (
    nodeOrEdge: string | null,
    step: V2Step,
    type: string
  ) => void;

  // UI Actions
  setSelectedNode: (id: string | null) => void;
  setSelectedEdge: (id: string | null) => void;
  setOpenGlobalEditor: (open: boolean) => void;
  setStepEditorOpenForNode: (nodeId: string | null) => void;
  setIsLayouted: (isLayouted: boolean) => void;

  // Validation
  validateStep: (step: V2Step, parent?: V2Step) => boolean;
  validateWorkflow: (definitionV1: Definition) => boolean;
  validationErrors: Record<string, string | null>;

  // Workflow Actions
  saveWorkflow: () => Promise<void>;

  // Lifecycle
  initialize: (
    yamlString: string,
    providers: Provider[],
    workflowId?: string
  ) => void;
  cleanup: () => void;

  // Internal Actions
  updateDefinition: () => void;

  // Add new method for empty workflow creation
  initializeEmpty: (options?: {
    alertName?: string;
    alertSource?: string;
    workflowId?: string;
  }) => void;

  // Node Data Updates
  updateSelectedNodeData: (key: string, value: any) => void;

  // Flow Operations
  setNodes: (nodes: FlowNode[]) => void;
  setEdges: (edges: Edge[]) => void;
  onNodesChange: (changes: any) => void;
  onEdgesChange: (changes: any) => void;
  onConnect: (connection: any) => void;
  onDragOver: (event: React.DragEvent) => void;
  onDrop: (
    event: React.DragEvent,
    getPosition: () => { x: number; y: number }
  ) => void;
  setToolBoxConfig: (config: any) => void;

  // Test Run State
  runRequestCount: number;

  // Test Run Actions
  triggerTestRun: () => void;

  // Layout Operations
  onLayout: (options: {
    direction: string;
    useInitialNodes?: boolean;
    initialNodes?: FlowNode[];
    initialEdges?: Edge[];
  }) => void;
  getLayoutedElements: (
    nodes: FlowNode[],
    edges: Edge[],
    options?: any
  ) => {
    nodes: FlowNode[];
    edges: Edge[];
  };

  // Add isLoading state
  isLoading: boolean;

  // Add setter for save function
  setSaveWorkflow: (fn: () => Promise<void>) => void;
}

const INITIAL_STATE = {
  nodes: [],
  edges: [],
  v2Properties: {},
  definition: {
    value: {
      sequence: [],
      properties: {},
    },
    isValid: false,
  },
  selectedNode: null,
  selectedEdge: null,
  errorNodes: [],
  openGlobalEditor: true,
  stepEditorOpenForNode: null,
  toolboxConfiguration: { groups: [] },
  isLayouted: false,
  isSaving: false,
  isPendingSync: false,
  lastSyncedAt: 0,
  canDeploy: false,
  changes: 0,
  validationErrors: {},
  runRequestCount: 0,
  isLoading: true,
};

export const useWorkflowStore = create<WorkflowStore>()(
  devtools((set, get) => ({
    ...INITIAL_STATE,

    // Core Flow Actions
    updateNodes: (nodes) => {
      set({
        nodes,
        isPendingSync: true,
        changes: get().changes + 1,
      });
      get().updateDefinition();
    },

    updateEdges: (edges) => {
      set({
        edges,
        isPendingSync: true,
        changes: get().changes + 1,
      });
      get().updateDefinition();
    },

    updateV2Properties: async (properties) => {
      console.log("xxx updateV2Properties");
      set({
        v2Properties: { ...get().v2Properties, ...properties },
        isPendingSync: true,
        changes: get().changes + 1,
      });

      get().updateDefinition();
    },

    // Internal helper for definition updates
    updateDefinition: () => {
      const { nodes, edges, v2Properties } = get();
      const newDefinition = getDefinitionFromNodesEdgesProperties(
        nodes,
        edges,
        v2Properties,
        undefined
      );
      const isValid = get().validateWorkflow(newDefinition);

      const lastSyncedAt = Date.now();
      set({
        definition: wrapDefinitionV2({
          ...newDefinition,
          isValid,
        }),
        isPendingSync: false,
        lastSyncedAt,
      });
    },

    // Node/Edge Queries
    getNodeById: (id) =>
      id ? get().nodes.find((node) => node.id === id) : undefined,

    getEdgeById: (id) => get().edges.find((edge) => edge.id === id),

    getNextEdge: (nodeId) => {
      const edge = get().edges.find((e) => e.source === nodeId);
      if (!edge) {
        return null;
      }
      return edge;
    },

    // Node/Edge Management
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
      get().updateDefinition();
      get().onLayout({ direction: "DOWN" });
    },

    updateNode: (node) => {
      set((state) => ({
        nodes: state.nodes.map((n) => (n.id === node.id ? node : n)),
        isPendingSync: true,
        changes: state.changes + 1,
      }));
      get().updateDefinition();
    },

    updateEdge: (id, key, value) => {
      set((state) => ({
        edges: state.edges.map((e) =>
          e.id === id ? { ...e, [key]: value } : e
        ),
        isPendingSync: true,
        changes: state.changes + 1,
      }));
      get().updateDefinition();
    },

    duplicateNode: (node) => {
      const newId = uuidv4();
      const newNode = {
        ...node,
        id: newId,
        data: { ...node.data, id: newId },
        position: {
          x: node.position.x + 100,
          y: node.position.y + 100,
        },
      };

      set((state) => ({
        nodes: [...state.nodes, newNode],
        isPendingSync: true,
        changes: state.changes + 1,
      }));
      get().updateDefinition();
    },

    // UI Actions
    setSelectedNode: (id) =>
      set({
        selectedNode: id,
        selectedEdge: null,
        openGlobalEditor: false,
      }),

    setSelectedEdge: (id) =>
      set({
        selectedEdge: id,
        selectedNode: null,
        openGlobalEditor: true,
      }),

    setOpenGlobalEditor: (open) => set({ openGlobalEditor: open }),

    setStepEditorOpenForNode: (nodeId) =>
      set({
        stepEditorOpenForNode: nodeId,
        openGlobalEditor: false,
      }),

    setIsLayouted: (isLayouted) => set({ isLayouted }),

    // Validation
    validateWorkflow: (definition: Definition) => {
      const validationErrors = {};
      for (let step of definition.sequence) {
        const validatorResult = stepValidatorV2(step);
        if (validatorResult.error) {
          validationErrors[step.name] = validatorResult.error.message;
        }
      }

      const globalValidationResult = globalValidatorV2(definition);

      const isValid =
        Object.values(validationErrors).every((error) => error === null) &&
        globalValidationResult.isValid;

      set({
        validationErrors: {
          ...validationErrors,
          [globalValidationResult.error?.nodeId ?? "global"]:
            globalValidationResult.error?.message ?? null,
        },
      });

      return isValid;
    },

    // Workflow Actions
    saveWorkflow: async () => {
      throw new Error("Save workflow not initialized");
    },

    // Complex Node Management
    addNodeBetween: (nodeOrEdge, step, type) => {
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

      // Validation checks
      if (sourceId !== "trigger_start" && isTriggerComponent) {
        return;
      }
      if (sourceId === "trigger_start" && !isTriggerComponent) {
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
      if (targetIndex === -1) return;

      if (sourceId === "trigger_start") {
        targetId = "trigger_end";
      }

      const newNodeId = isTriggerComponent ? step.id : uuidv4();
      const cloneStep = { ...step, id: newNodeId };
      const edges = get().edges;

      // Process new workflow structure
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
          cloneStep,
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

      // Update edges
      const finalEdges = [
        ...newEdges,
        ...(edges.filter(
          (edge) => !(edge.source === sourceId && edge.target === targetId)
        ) || []),
      ];

      // Update nodes
      const isNested = !!(
        nodes[targetIndex]?.isNested || nodes[sourceIndex]?.isNested
      );
      newNodes = newNodes.map((node) => ({ ...node, isNested }));
      newNodes = [
        ...nodes.slice(0, targetIndex),
        ...newNodes,
        ...nodes.slice(targetIndex),
      ];

      // Update store
      set({
        edges: finalEdges,
        nodes: newNodes,
        isLayouted: false,
        changes: get().changes + 1,
        isPendingSync: true,
      });

      // Handle special node types
      if (["interval", "manual", "alert", "incident"].includes(newNodeId)) {
        const specialNodeProps =
          newNodeId === "alert" ? {} : newNodeId === "incident" ? {} : "";

        set((state) => ({
          v2Properties: {
            ...state.v2Properties,
            [newNodeId]: specialNodeProps,
          },
        }));
      }

      // Update selection
      if (type === "edge") {
        set({ selectedEdge: edges[edges.length - 1]?.id });
      } else if (type === "node") {
        set({ selectedNode: nodeOrEdge });
      } else if (newNodeId) {
        set({ selectedNode: newNodeId });
      }

      get().updateDefinition();
      get().onLayout({ direction: "DOWN" });
    },

    // Update initialize to handle layout
    initialize: (yamlString, providers, workflowId) => {
      console.log("xxx initialize", yamlString, workflowId);
      set({ ...INITIAL_STATE, isLoading: true });

      if (!yamlString) {
        throw new Error("No YAML string provided");
      }

      try {
        const definition = parseWorkflow(yamlString, providers);
        const sequenceWithStartAndEndAndTriggers = [
          {
            id: "start",
            type: "start",
            componentType: "start",
            properties: {},
            isLayouted: false,
            name: "start",
          } as V2Step,
          ...getTriggerSteps(definition.properties),
          ...(definition.sequence || []),
          {
            id: "end",
            type: "end",
            componentType: "end",
            properties: {},
            isLayouted: false,
            name: "end",
          } as V2Step,
        ];
        const intialPositon = { x: 0, y: 50 };
        let { nodes, edges } = processWorkflowV2(
          sequenceWithStartAndEndAndTriggers,
          intialPositon,
          true
        );

        const isValid = get().validateWorkflow(definition);
        set({
          workflowId,
          nodes,
          edges,
          v2Properties: definition.properties || {},
          definition: wrapDefinitionV2({
            ...definition,
            isValid,
          }),
          lastSyncedAt: Date.now(),
          isLoading: false,
          toolboxConfiguration: getToolboxConfiguration(providers),
        });

        // Trigger layout after setting initial nodes/edges
        get().onLayout({ direction: "DOWN" });
      } catch (error) {
        console.error("Failed to initialize workflow:", error);
        const errorMessage =
          error instanceof YAMLException
            ? `Invalid YAML: ${error.message}`
            : "Failed to initialize workflow";

        set((state) => ({
          validationErrors: {
            ...state.validationErrors,
            global: errorMessage,
          },
          isLoading: false,
        }));
      }
    },

    cleanup: () => {
      set(INITIAL_STATE);
    },

    // Add new method for empty workflow creation
    // TODO: fix
    initializeEmpty: (options = {}) => {
      set(INITIAL_STATE);

      try {
        const workflowId = options.workflowId || uuidv4();
        let triggers = {};

        if (options.alertName && options.alertSource) {
          triggers = {
            alert: {
              source: options.alertSource,
              name: options.alertName,
            },
          };
        }

        const definition = wrapDefinitionV2({
          ...generateWorkflow(
            workflowId,
            "", // name
            "", // description
            false, // disabled
            {}, // consts
            [], // steps
            [], // conditions
            triggers
          ),
          isValid: true,
        });

        const { nodes, edges } = processWorkflowV2(definition.value.sequence, {
          x: 0,
          y: 0,
        });

        set({
          nodes,
          edges,
          v2Properties: definition.value.properties || {},
          definition,
          isLayouted: true,
          lastSyncedAt: Date.now(),
        });

        get().validateWorkflow(definition.value);
      } catch (error) {
        console.error("Failed to initialize empty workflow:", error);
        set((state) => ({
          validationErrors: {
            ...state.validationErrors,
            global: "Failed to initialize empty workflow",
          },
        }));
      }
    },

    // Node Data Updates
    updateSelectedNodeData: (key, value) => {
      console.log("xxx updateSelectedNodeData", key, value);
      const currentSelectedNode = get().selectedNode;
      console.log("xxx currentSelectedNode", currentSelectedNode);
      console.log("xxx nodes", get().nodes);
      if (!currentSelectedNode) {
        return;
      }
      const updatedNodes = get().nodes.map((node) => {
        if (node.id === currentSelectedNode) {
          if (value) {
            node.data[key] = value;
          } else {
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

      get().updateDefinition();
    },

    // Flow Operations
    setNodes: (nodes) => {
      set({ nodes });
      get().updateDefinition();
    },

    setEdges: (edges) => {
      set({ edges });
      get().updateDefinition();
    },

    onNodesChange: (changes) => {
      set((state) => ({
        nodes: applyNodeChanges(changes, state.nodes),
        isPendingSync: true,
        changes: state.changes + 1,
      }));
      get().updateDefinition();
    },

    onEdgesChange: (changes) => {
      set((state) => ({
        edges: applyEdgeChanges(changes, state.edges),
        isPendingSync: true,
        changes: state.changes + 1,
      }));
      get().updateDefinition();
    },

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
      get().updateDefinition();
    },

    onDragOver: (event) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
    },
    onDrop: (event, getPosition) => {
      event.preventDefault();
      event.stopPropagation();

      try {
        let step: any = event.dataTransfer.getData("application/reactflow");
        if (!step) {
          return;
        }
        step = JSON.parse(step);
        if (!step) return;

        // Use the getPosition function to get flow coordinates
        const position = getPosition();

        const newUuid = uuidv4();
        const newNode = {
          id: newUuid,
          type: "custom",
          position,
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

    setToolBoxConfig: (config) => {
      set({ toolboxConfiguration: config });
    },

    // Test Run Actions
    triggerTestRun: () => {
      set((state) => ({
        runRequestCount: state.runRequestCount + 1,
      }));
    },

    // Layout Operations
    getLayoutedElements: (nodes, edges, options = {}) => {
      const isHorizontal = options?.["elk.direction"] === "RIGHT";
      const dagreGraph = new graphlib.Graph();
      dagreGraph.setDefaultEdgeLabel(() => ({}));

      dagreGraph.setGraph({
        rankdir: isHorizontal ? "LR" : "TB",
        nodesep: 80,
        ranksep: 80,
        edgesep: 80,
      });

      nodes.forEach((node) => {
        const type = node?.data?.type
          ?.replace("step-", "")
          ?.replace("action-", "")
          ?.replace("condition-", "")
          ?.replace("__end", "");

        let width = ["start", "end"].includes(type) ? 80 : 280;
        let height = 80;

        if (node.id === "trigger_start" || node.id === "trigger_end") {
          width = 150;
          height = 40;
        }

        if (node.id === "start") {
          width = 0;
          height = 0;
        }

        dagreGraph.setNode(node.id, { width, height });
      });

      edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
      });

      dagre.layout(dagreGraph);

      const layoutedNodes = nodes.map((node) => {
        const dagreNode = dagreGraph.node(node.id);
        return {
          ...node,
          targetPosition: isHorizontal ? "left" : "top",
          sourcePosition: isHorizontal ? "right" : "bottom",
          style: {
            ...node.style,
            width: dagreNode.width as number,
            height: dagreNode.height as number,
          },
          position: {
            x: dagreNode.x - dagreNode.width / 2,
            y: dagreNode.y - dagreNode.height / 2,
          },
        };
      });

      return {
        nodes: layoutedNodes,
        edges,
      };
    },

    onLayout: ({
      direction,
      useInitialNodes = false,
      initialNodes,
      initialEdges,
    }) => {
      const opts = { "elk.direction": direction };
      const ns = useInitialNodes ? initialNodes : get().nodes;
      const es = useInitialNodes ? initialEdges : get().edges;

      const { nodes: layoutedNodes, edges: layoutedEdges } =
        get().getLayoutedElements(ns, es, opts);

      const finalEdges = layoutedEdges.map((edge: Edge) => ({
        ...edge,
        animated: !!edge?.target?.includes("empty"),
        data: { ...edge.data, isLayouted: true },
      }));

      const finalNodes = layoutedNodes.map((node: FlowNode) => ({
        ...node,
        data: { ...node.data, isLayouted: true },
      }));

      set({
        nodes: finalNodes,
        edges: finalEdges,
        isLayouted: true,
      });
    },

    // Add setter for save function
    setSaveWorkflow: (fn) => set({ saveWorkflow: fn }),
  }))
);
