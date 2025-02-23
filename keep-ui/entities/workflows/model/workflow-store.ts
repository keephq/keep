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
  getTriggerSteps,
  reConstructWorklowToDefinition,
} from "utils/reactFlow";
import { createDefaultNodeV2 } from "@/utils/reactFlow";
import {
  V2Step,
  StoreSet,
  StoreGet,
  FlowStateValues,
  FlowState,
  FlowNode,
  Definition,
  V2StepTemplateSchema,
  V2EndStep,
  V2StartStep,
  V2StepTrigger,
  V2StepTemplate,
  V2StepTriggerSchema,
  ProvidersConfiguration,
} from "@/entities/workflows";
import { validateStepPure, validateGlobalPure } from "./validation";
import { getLayoutedWorkflowElements } from "../lib/getLayoutedWorkflowElements";
import { wrapDefinitionV2 } from "@/entities/workflows/lib/parser";
import { showErrorToast } from "@/shared/ui/utils/showErrorToast";
import { ZodError } from "zod";
import { fromError } from "zod-validation-error";
import {
  edgeCanAddStep,
  edgeCanAddTrigger,
  getToolboxConfiguration,
} from "@/features/workflows/builder/lib/utils";
import { Provider } from "@/shared/api/providers";

class KeepWorkflowStoreError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "KeepWorkflowStoreError";
  }
}
const PROTECTED_NODE_IDS = ["start", "end", "trigger_start", "trigger_end"];

/**
 * Add a node between two edges
 * @param nodeOrEdgeId - The id of the node or edge to add the new node between
 * @param rawStep - The step to add
 * @param type - The type of the node or edge
 * @param set - The set function
 * @param get - The get function
 * @returns The id of the new node
 * @throws KeepWorkflowStoreError if the node or edge or step is not defined
 * @throws ZodError if the step is not valid
 */
function addNodeBetween(
  nodeOrEdgeId: string,
  rawStep: V2StepTemplate | V2StepTrigger,
  type: "node" | "edge",
  set: StoreSet,
  get: StoreGet
) {
  if (!rawStep) {
    throw new KeepWorkflowStoreError("Step is not defined");
  }

  if (!nodeOrEdgeId) {
    throw new KeepWorkflowStoreError("Node or edge id is not defined");
  }

  const isTriggerComponent = rawStep.componentType === "trigger";
  let step: V2StepTemplate | V2StepTrigger;

  if (isTriggerComponent) {
    step = V2StepTriggerSchema.parse(rawStep);
  } else {
    step = V2StepTemplateSchema.parse(rawStep);
  }

  let edge = {} as Edge;
  if (type === "node") {
    edge = get().edges.find((edge) => edge.target === nodeOrEdgeId) as Edge;
    if (!edge) {
      throw new KeepWorkflowStoreError(
        `Edge with target ${nodeOrEdgeId} not found`
      );
    }
  }

  if (type === "edge") {
    edge = get().edges.find((edge) => edge.id === nodeOrEdgeId) as Edge;
    if (!edge) {
      throw new KeepWorkflowStoreError(
        `Edge with id ${nodeOrEdgeId} not found`
      );
    }
  }

  if (isTriggerComponent && !edgeCanAddTrigger(edge.source, edge.target)) {
    throw new KeepWorkflowStoreError(`Edge ${edge.id} cannot add trigger`);
  }

  if (!isTriggerComponent && !edgeCanAddStep(edge.source, edge.target)) {
    throw new KeepWorkflowStoreError(`Edge ${edge.id} cannot add step`);
  }

  let { source: sourceId, target: targetId } = edge || {};
  if (!sourceId) {
    throw new KeepWorkflowStoreError(
      `Source is not defined for edge ${edge.id}`
    );
  }
  if (!targetId) {
    throw new KeepWorkflowStoreError(
      `Target is not defined for edge ${edge.id}`
    );
  }

  if (sourceId !== "trigger_start" && isTriggerComponent) {
    throw new KeepWorkflowStoreError(
      `Trigger is only allowed at the start of the workflow. Attempted to add trigger at edge ${edge.id}`
    );
  }

  if (sourceId == "trigger_start" && !isTriggerComponent) {
    throw new KeepWorkflowStoreError(
      `Only trigger can be added at the start of the workflow. Attempted to add step at edge ${edge.id}`
    );
  }

  const nodes = get().nodes;
  // Return if the trigger is already in the workflow
  if (isTriggerComponent && nodes.find((node) => node && step.id === node.id)) {
    throw new KeepWorkflowStoreError(
      `This ${step.type} trigger is already in the workflow`
    );
  }

  let targetIndex = nodes.findIndex((node) => node.id === targetId);
  const sourceIndex = nodes.findIndex((node) => node.id === sourceId);
  if (targetIndex == -1) {
    throw new KeepWorkflowStoreError(
      `Target node with id ${targetId} not found`
    );
  }

  if (sourceId === "trigger_start") {
    targetId = "trigger_end";
  }
  // for triggers, we use the id from the step, for steps we generate a new id
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
    lastChangedAt: Date.now(),
  });

  switch (newNodeId) {
    case "interval":
    case "manual": {
      set({
        v2Properties: {
          ...get().v2Properties,
          [newNodeId]: newStep.properties?.[newNodeId] ?? "",
        },
      });
      break;
    }
    case "alert": {
      set({
        v2Properties: {
          ...get().v2Properties,
          [newNodeId]: newStep.properties?.[newNodeId] ?? {},
        },
      });
      break;
    }
    case "incident": {
      set({
        v2Properties: {
          ...get().v2Properties,
          [newNodeId]: newStep.properties?.[newNodeId] ?? {},
        },
      });
      break;
    }
  }

  get().onLayout({ direction: "DOWN" });
  get().updateDefinition();

  return newNodeId;
}

// TODO: break down the state into smaller pieces
// - core worfklow state (definition, nodes, edges, selectedNode, etc)
// - editor state (editorOpen, stepEditorOpenForNode)
// - builder state (toolbox, selectedEdge, selectedNode, isLayouted, etc)
const defaultState: FlowStateValues = {
  workflowId: null,
  nodes: [],
  edges: [],
  selectedNode: null,
  v2Properties: {},
  editorOpen: false,
  toolboxConfiguration: null,
  providers: null,
  installedProviders: null,
  isInitialized: false,
  isLayouted: false,
  selectedEdge: null,
  changes: 0,
  isEditorSyncedWithNodes: true,
  lastChangedAt: 0,
  lastDeployedAt: 0,
  canDeploy: false,
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
    triggerSave: () =>
      set((state) => ({ saveRequestCount: state.saveRequestCount + 1 })),
    triggerRun: () =>
      set((state) => ({ runRequestCount: state.runRequestCount + 1 })),
    setIsSaving: (state: boolean) => set({ isSaving: state }),
    setCanDeploy: (deploy) => set({ canDeploy: deploy }),
    setEditorSynced: (sync) => set({ isEditorSyncedWithNodes: sync }),
    setLastDeployedAt: (deployedAt) => set({ lastDeployedAt: deployedAt }),
    setSelectedEdge: (id) => set({ selectedEdge: id, selectedNode: null }),
    setIsLayouted: (isLayouted) => set({ isLayouted }),
    getEdgeById: (id) => get().edges.find((edge) => edge.id === id),
    addNodeBetween: (
      nodeOrEdgeId: string,
      step: V2StepTemplate | V2StepTrigger,
      type: "node" | "edge"
    ) => {
      const newNodeId = addNodeBetween(nodeOrEdgeId, step, type, set, get);
      set({ selectedNode: newNodeId, selectedEdge: null });
      return newNodeId ?? null;
    },
    addNodeBetweenSafe: (
      nodeOrEdgeId: string,
      step: V2StepTemplate | V2StepTrigger,
      type: "node" | "edge"
    ) => {
      try {
        const newNodeId = addNodeBetween(nodeOrEdgeId, step, type, set, get);
        set({ selectedNode: newNodeId, selectedEdge: null });
        return newNodeId ?? null;
      } catch (error) {
        if (error instanceof ZodError) {
          // TODO: extract meaningful error from ZodError
          const validationError = fromError(error);
          showErrorToast(validationError);
          console.error(error);
        } else {
          showErrorToast(error);
          console.error(error);
        }
        return null;
      }
    },
    setProviders: (providers: Provider[]) => set({ providers }),
    setInstalledProviders: (installedProviders: Provider[]) =>
      set({ installedProviders }),
    setEditorOpen: (open) => set({ editorOpen: open }),
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
          lastChangedAt: Date.now(),
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
        const error = validateStepPure(
          step,
          get().providers ?? [],
          get().installedProviders ?? []
        );
        if (step.componentType === "switch") {
          [...step.branches.true, ...step.branches.false].forEach((branch) => {
            const error = validateStepPure(
              branch,
              get().providers ?? [],
              get().installedProviders ?? []
            );
            if (error) {
              validationErrors[branch.name || branch.id] = error;
              isValid = false;
            }
          });
        }
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
        isEditorSyncedWithNodes: true,
      });
    },
    updateV2Properties: (properties) => {
      const updatedProperties = { ...get().v2Properties, ...properties };
      set({
        v2Properties: updatedProperties,
        changes: get().changes + 1,
        lastChangedAt: Date.now(),
      });
      get().updateDefinition();
    },
    setSelectedNode: (id) => {
      set({
        selectedNode: id || null,
        selectedEdge: null,
      });
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
        return [];
      }
      if (PROTECTED_NODE_IDS.includes(ids)) {
        throw new KeepWorkflowStoreError("Cannot delete protected node");
      }
      const nodes = get().nodes;
      const nodeStartIndex = nodes.findIndex((node) => ids == node.id);
      if (nodeStartIndex === -1) {
        return [];
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
        editorOpen: true,
      });
      get().onLayout({ direction: "DOWN" });
      get().updateDefinition();

      return [ids];
    },
    getNextEdge: (nodeId: string) => {
      const node = get().getNodeById(nodeId);
      if (!node) {
        throw new KeepWorkflowStoreError("Node not found");
      }
      // TODO: handle multiple edges
      const edges = get().edges.filter((e) => e.source === nodeId);
      if (!edges.length) {
        throw new KeepWorkflowStoreError("Edge not found");
      }
      if (node.data.componentType === "switch") {
        // If the node is a switch, return the second edge, because "true" is the second edge
        return edges[1];
      }
      return edges[0];
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
      { providers, installedProviders }: ProvidersConfiguration
    ) =>
      initializeWorkflow(
        workflowId,
        { providers, installedProviders },
        set,
        get
      ),
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

function initializeWorkflow(
  workflowId: string | null,
  { providers, installedProviders }: ProvidersConfiguration,
  set: StoreSet,
  get: StoreGet
) {
  const definition = get().definition;
  if (definition === null) {
    throw new Error("Definition should be set before initializing workflow");
  }
  set({ isLoading: true });
  let parsedWorkflow = definition?.value;
  const name = parsedWorkflow?.properties?.name;

  const toolboxConfiguration = getToolboxConfiguration(providers);

  const fullSequence = [
    {
      id: "start",
      type: "start",
      componentType: "start",
      properties: {},
      isLayouted: false,
      name: "start",
    } as V2StartStep,
    ...getTriggerSteps(parsedWorkflow?.properties),
    ...(parsedWorkflow?.sequence || []),
    {
      id: "end",
      type: "end",
      componentType: "end",
      properties: {},
      isLayouted: false,
      name: "end",
    } as V2EndStep,
  ];
  const initialPosition = { x: 0, y: 50 };
  let { nodes, edges } = processWorkflowV2(fullSequence, initialPosition, true);
  set({
    workflowId,
    selectedNode: null,
    isLayouted: false,
    nodes,
    edges,
    v2Properties: { ...(parsedWorkflow?.properties ?? {}), name },
    providers,
    installedProviders,
    toolboxConfiguration,
    isLoading: false,
    isInitialized: true,
    // If it's a new workflow (workflowId = null), we want to open the editor because metadata fields in there
    editorOpen: !workflowId,
  });
  get().onLayout({ direction: "DOWN" });
  get().updateDefinition();
}
