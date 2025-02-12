import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { v4 as uuidv4 } from "uuid";
import {
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  Edge,
} from "@xyflow/react";
import {
  createCustomEdgeMeta,
  processWorkflowV2,
  getTriggerStep,
  reConstructWorklowToDefinition,
} from "utils/reactFlow";
import { createDefaultNodeV2 } from "../../../utils/reactFlow";
import {
  V2Step,
  StoreSet,
  StoreGet,
  FlowStateValues,
  FlowState,
  FlowNode,
  Definition,
  ToolboxConfiguration,
} from "@/entities/workflows";
import { validateStepPure, validateGlobalPure } from "./validation";
import { getLayoutedWorkflowElements } from "../lib/getLayoutedWorkflowElements";
import { wrapDefinitionV2 } from "@/entities/workflows/lib/parser";

function addNodeBetween(
  nodeOrEdgeId: string,
  step: V2Step,
  type: "node" | "edge",
  set: StoreSet,
  get: StoreGet
) {
  if (!nodeOrEdgeId || !step) {
    console.error("addNodeBetween: Node or edge or step is not defined");
    return;
  }
  let edge = {} as Edge;
  if (type === "node") {
    edge = get().edges.find((edge) => edge.target === nodeOrEdgeId) as Edge;
  }

  if (type === "edge") {
    edge = get().edges.find((edge) => edge.id === nodeOrEdgeId) as Edge;
  }

  let { source: sourceId, target: targetId } = edge || {};
  if (!sourceId || !targetId) {
    console.error("addNodeBetween: Source or target is not defined");
    return;
  }

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
    set({ selectedNode: nodeOrEdgeId });
  }

  switch (newNodeId) {
    case "interval":
    case "manual": {
      set({ v2Properties: { ...get().v2Properties, [newNodeId]: "" } });
      break;
    }
    case "alert": {
      set({ v2Properties: { ...get().v2Properties, [newNodeId]: {} } });
      break;
    }
    case "incident": {
      set({ v2Properties: { ...get().v2Properties, [newNodeId]: {} } });
      break;
    }
  }

  get().onLayout({ direction: "DOWN" });
  get().updateDefinition();
}

const defaultState: FlowStateValues = {
  workflowId: null,
  nodes: [],
  edges: [],
  selectedNode: null,
  v2Properties: {},
  openGlobalEditor: true,
  stepEditorOpenForNode: null,
  toolboxConfiguration: null,
  isLayouted: false,
  selectedEdge: null,
  changes: 0,
  synced: true,
  canDeploy: false,
  buttonsEnabled: false,
  saveRequestCount: 0,
  runRequestCount: 0,
  isSaving: false,
  definition: null,
  isLoading: false,
  validationErrors: {},
};

export const useWorkflowStore = create<FlowState>()(
  devtools((set, get) => ({
    ...defaultState,
    setDefinition: (def) => set({ definition: def }),
    setIsLoading: (loading) => set({ isLoading: loading }),
    setButtonsEnabled: (state: boolean) => set({ buttonsEnabled: state }),
    triggerSave: () =>
      set((state) => ({ saveRequestCount: state.saveRequestCount + 1 })),
    triggerRun: () =>
      set((state) => ({ runRequestCount: state.runRequestCount + 1 })),
    setIsSaving: (state: boolean) => set({ isSaving: state }),
    setCanDeploy: (deploy) => set({ canDeploy: deploy }),
    setSynced: (sync) => set({ synced: sync }),
    setSelectedEdge: (id) =>
      set({ selectedEdge: id, selectedNode: null, openGlobalEditor: true }),
    setIsLayouted: (isLayouted) => set({ isLayouted }),
    addNodeBetween: (
      nodeOrEdgeId: string,
      step: V2Step,
      type: "node" | "edge"
    ) => {
      addNodeBetween(nodeOrEdgeId, step, type, set, get);
    },
    setToolBoxConfig: (config: ToolboxConfiguration) =>
      set({ toolboxConfiguration: config }),
    setOpneGlobalEditor: (open) => set({ openGlobalEditor: open }),
    updateSelectedNodeData: (key, value) => {
      const currentSelectedNode = get().selectedNode;
      if (currentSelectedNode) {
        const updatedNodes = get().nodes.map((node) => {
          if (node.id === currentSelectedNode) {
            //properties changes  should not reconstructed the defintion. only recontrreconstructing if there are any structural changes are done on the flow.
            if (value !== undefined && value !== null) {
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
      }
    },
    updateDefinition: () => {
      // Immediately update definition with new properties
      const { nodes, edges } = get();
      const { sequence, properties: newProperties } =
        reConstructWorklowToDefinition({
          nodes,
          edges,
          properties: get().v2Properties,
        });

      // Use validators to check if the workflow is valid
      let isValid = true;
      const validationErrors: Record<string, string> = {};
      const definition: Definition = { sequence, properties: newProperties };

      const result = validateGlobalPure(definition);
      if (result) {
        result.forEach(([key, error]) => {
          validationErrors[key] = error;
        });
        isValid = result.length === 0;
      }

      // Check each step's validity
      for (const step of sequence) {
        const error = validateStepPure(step);
        if (error) {
          validationErrors[step.name || step.id] = error;
          isValid = false;
        }
      }

      // We allow deployment even if there are provider errors, as the user can fix them later
      const canDeploy =
        Object.values(validationErrors).filter(
          (error) => !error.includes("provider")
        ).length === 0;

      set({
        definition: wrapDefinitionV2({
          sequence,
          properties: newProperties,
          isValid,
        }),
        validationErrors,
        canDeploy,
        synced: true,
      });
    },
    updateV2Properties: (properties) => {
      const updatedProperties = { ...get().v2Properties, ...properties };
      set({ v2Properties: updatedProperties, changes: get().changes + 1 });
      get().updateDefinition();
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
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = "move";
      }
    },
    onDrop: (event, screenToFlowPosition) => {
      event.preventDefault();
      event.stopPropagation();

      try {
        const dataTransfer = event.dataTransfer;
        if (!dataTransfer) return;

        let step: any = dataTransfer.getData("application/reactflow");
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
    getNodeById: (id) => get().nodes.find((node) => node.id === id),
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
      get().onLayout({ direction: "DOWN" });
      get().updateDefinition();
    },
    // used to reset the store to the initial state, on builder unmount
    reset: () => set(defaultState),
    onLayout: (params: {
      direction: string;
      useInitialNodes?: boolean;
      initialNodes?: FlowNode[];
      initialEdges?: Edge[];
    }) => onLayout(params, set, get),
    initializeWorkflow: (
      workflowId: string | null,
      toolboxConfiguration: ToolboxConfiguration
    ) => initializeWorkflow(workflowId, toolboxConfiguration, set, get),
  }))
);

function onLayout(
  {
    direction,
    useInitialNodes = false,
    initialNodes = [],
    initialEdges = [],
  }: {
    direction: string;
    useInitialNodes?: boolean;
    initialNodes?: FlowNode[];
    initialEdges?: Edge[];
  },
  set: StoreSet,
  get: StoreGet
) {
  const opts = { "elk.direction": direction };
  const ns = useInitialNodes ? initialNodes : get().nodes || [];
  const es = useInitialNodes ? initialEdges : get().edges || [];

  const { nodes: _layoutedNodes, edges: _layoutedEdges } =
    getLayoutedWorkflowElements(ns, es, opts);
  const layoutedEdges = _layoutedEdges.map((edge: Edge) => {
    return {
      ...edge,
      animated: !!edge?.target?.includes("empty"),
      data: { ...edge.data, isLayouted: true },
    };
  });
  const layoutedNodes = _layoutedNodes.map((node: FlowNode) => {
    return {
      ...node,
      data: { ...node.data, isLayouted: true },
    };
  });
  set({
    nodes: layoutedNodes,
    edges: layoutedEdges,
    isLayouted: true,
  });
}

async function initializeWorkflow(
  workflowId: string | null,
  toolboxConfiguration: ToolboxConfiguration,
  set: StoreSet,
  get: StoreGet
) {
  const definition = get().definition;
  if (definition === null) {
    throw new Error("Definition should be set before initializing workflow");
  }
  set({ isLoading: true });
  let parsedWorkflow = definition?.value;
  const name =
    parsedWorkflow?.properties?.name || parsedWorkflow?.properties?.id;

  const sequences = [
    {
      id: "start",
      type: "start",
      componentType: "start",
      properties: {},
      isLayouted: false,
      name: "start",
    } as V2Step,
    ...getTriggerStep(parsedWorkflow?.properties),
    ...(parsedWorkflow?.sequence || []),
    {
      id: "end",
      type: "end",
      componentType: "end",
      properties: {},
      isLayouted: false,
      name: "end",
    } as V2Step,
  ];
  const initialPosition = { x: 0, y: 50 };
  let { nodes, edges } = processWorkflowV2(sequences, initialPosition, true);
  set({
    workflowId,
    selectedNode: null,
    isLayouted: false,
    nodes,
    edges,
    v2Properties: { ...(parsedWorkflow?.properties ?? {}), name },
    toolboxConfiguration,
    isLoading: false,
  });
  get().onLayout({ direction: "DOWN" });
  get().updateDefinition();
}
