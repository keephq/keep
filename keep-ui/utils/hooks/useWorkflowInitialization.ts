import { useEffect, useState, useCallback } from "react";
import { Edge, useReactFlow } from "@xyflow/react";
import { useStore } from "@/app/(keep)/workflows/builder/builder-store";
import dagre, { graphlib } from "@dagrejs/dagre";
import { processWorkflowV2, getTriggerStep } from "utils/reactFlow";
import {
  FlowNode,
  ReactFlowDefinition,
  ToolboxConfiguration,
  V2Step,
} from "@/app/(keep)/workflows/builder/types";

const getLayoutedElements = (
  nodes: FlowNode[],
  edges: Edge[],
  options = {}
) => {
  // @ts-ignore
  const isHorizontal = options?.["elk.direction"] === "RIGHT";
  const dagreGraph = new graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  // Set graph direction and spacing
  dagreGraph.setGraph({
    rankdir: isHorizontal ? "LR" : "TB",
    nodesep: 80,
    ranksep: 80,
    edgesep: 80,
  });

  // Add nodes to dagre graph
  nodes.forEach((node) => {
    const type = node?.data?.type
      ?.replace("step-", "")
      ?.replace("action-", "")
      ?.replace("condition-", "")
      ?.replace("__end", "");

    let width = ["start", "end"].includes(type) ? 80 : 280;
    let height = 80;

    // Special case for trigger start and end nodes, which act as section headers
    if (node.id === "trigger_start" || node.id === "trigger_end") {
      width = 150;
      height = 40;
    }

    dagreGraph.setNode(node.id, { width, height });
  });

  // Add edges to dagre graph
  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  // Run the layout
  dagre.layout(dagreGraph);

  // Get the positioned nodes and edges
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
      // Dagre provides positions with the center of the node as origin
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
};

const useWorkflowInitialization = (
  definition: ReactFlowDefinition,
  toolboxConfiguration: ToolboxConfiguration
) => {
  const {
    changes,
    nodes,
    edges,
    setNodes,
    setEdges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    onDragOver,
    onDrop,
    setV2Properties,
    openGlobalEditor,
    selectedNode,
    setToolBoxConfig,
    isLayouted,
    setIsLayouted,
    setChanges,
    setSelectedNode,
    setFirstInitilisationDone,
  } = useStore();

  const [isLoading, setIsLoading] = useState(true);
  const { screenToFlowPosition } = useReactFlow();
  const [finalNodes, setFinalNodes] = useState<FlowNode[]>([]);
  const [finalEdges, setFinalEdges] = useState<Edge[]>([]);

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      onDrop(event, screenToFlowPosition);
    },
    [screenToFlowPosition]
  );

  const onLayout = useCallback(
    ({
      direction,
      useInitialNodes = false,
      initialNodes,
      initialEdges,
    }: {
      direction: string;
      useInitialNodes?: boolean;
      initialNodes?: FlowNode[];
      initialEdges?: Edge[];
    }) => {
      const opts = { "elk.direction": direction };
      const ns = useInitialNodes ? initialNodes : nodes;
      const es = useInitialNodes ? initialEdges : edges;

      const { nodes: _layoutedNodes, edges: _layoutedEdges } =
        // @ts-ignore
        getLayoutedElements(ns, es, opts);
      const layoutedEdges = _layoutedEdges.map((edge: Edge) => {
        return {
          ...edge,
          animated: !!edge?.target?.includes("empty"),
          data: { ...edge.data, isLayouted: true },
        };
      });
      // @ts-ignore
      const layoutedNodes = _layoutedNodes.map((node: FlowNode) => {
        return {
          ...node,
          data: { ...node.data, isLayouted: true },
        };
      });
      setNodes(layoutedNodes);
      setEdges(layoutedEdges);
      setIsLayouted(true);
      setFinalEdges(layoutedEdges);
      setFinalNodes(layoutedNodes);
    },
    [nodes, edges]
  );

  useEffect(() => {
    if (!isLayouted && nodes.length > 0) {
      onLayout({ direction: "DOWN" });
    }
  }, [nodes, edges]);

  useEffect(() => {
    const initializeWorkflow = async () => {
      setIsLoading(true);
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
      const intialPositon = { x: 0, y: 50 };
      let { nodes, edges } = processWorkflowV2(sequences, intialPositon, true);
      setSelectedNode(null);
      setFirstInitilisationDone(false);
      setIsLayouted(false);
      setNodes(nodes);
      setEdges(edges);
      setV2Properties({ ...(parsedWorkflow?.properties ?? {}), name });
      setChanges(1);
      setToolBoxConfig(toolboxConfiguration);
      setIsLoading(false);
    };
    if (changes === 0) {
      initializeWorkflow();
    }
  }, [changes]);

  return {
    nodes: finalNodes,
    edges: finalEdges,
    isLoading,
    onNodesChange: onNodesChange,
    onEdgesChange: onEdgesChange,
    onConnect: onConnect,
    onDragOver: onDragOver,
    onDrop: handleDrop,
    openGlobalEditor,
    selectedNode,
    setNodes,
    toolboxConfiguration,
    isLayouted,
  };
};

export default useWorkflowInitialization;
