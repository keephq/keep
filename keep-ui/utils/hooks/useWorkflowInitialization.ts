import { useEffect, useState, useCallback } from "react";
import { Edge, useReactFlow } from "@xyflow/react";
import useStore from "@/app/(keep)/workflows/builder/builder-store";
import { Provider } from "@/app/(keep)/providers/providers";
import ELK from "elkjs/lib/elk.bundled.js";
import { processWorkflowV2, getTriggerStep } from "utils/reactFlow";
import {
  Definition,
  FlowNode,
  ReactFlowDefinition,
  V2Step,
} from "@/app/(keep)/workflows/builder/types";

const layoutOptions = {
  "elk.nodeLabels.placement": "INSIDE V_CENTER H_BOTTOM",
  "elk.algorithm": "layered",
  "elk.direction": "BOTTOM",
  "org.eclipse.elk.layered.layering.strategy": "INTERACTIVE",
  "elk.edgeRouting": "ORTHOGONAL",
  "elk.layered.unnecessaryBendpoints": false,
  "elk.layered.spacing.edgeNodeBetweenLayers": "70",
  "org.eclipse.elk.layered.nodePlacement.bk.fixedAlignment": "BALANCED",
  "org.eclipse.elk.layered.cycleBreaking.strategy": "DEPTH_FIRST",
  "elk.insideSelfLoops.activate": true,
  separateConnectedComponents: "false",
  "spacing.componentComponent": "80",
  spacing: "80",
  "elk.spacing.nodeNodeBetweenLayers": "80",
  "elk.spacing.nodeNode": "120",
  "elk.layered.spacing.nodeNodeBetweenLayers": "80",
  portConstraints: "FIXED_ORDER",
  "nodeSize.constraints": "[MINIMUM_SIZE]",
  "elk.alignment": "CENTER",
  "elk.spacing.edgeNodeBetweenLayers": "70.0",
  "org.eclipse.elk.layoutAncestors": "true",
  "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
  "elk.layered.nodePlacement.outerSpacing": "30",
  "elk.layered.nodePlacement.outerPadding": "30",
  "elk.layered.edgeRouting.orthogonal": true,

  // Avoid bending towards nodes
  "elk.layered.allowEdgeLabelOverlap": false,
  "elk.layered.edgeRouting.avoidNodes": true,
  "elk.layered.edgeRouting.avoidEdges": true,
  "elk.layered.nodePlacement.nodeNodeOverlapAllowed": false,
  "elk.layered.consistentLevelSpacing": true,
};

const getLayoutedElements = (
  nodes: FlowNode[],
  edges: Edge[],
  options = {}
) => {
  // @ts-ignore
  const isHorizontal = options?.["elk.direction"] === "RIGHT";
  const elk = new ELK();

  const graph = {
    id: "root",
    layoutOptions: options,
    children: nodes.map((node) => {
      const type = node?.data?.type
        ?.replace("step-", "")
        ?.replace("action-", "")
        ?.replace("condition-", "")
        ?.replace("__end", "");
      return {
        ...node,
        // Adjust the target and source handle positions based on the layout
        // direction.
        targetPosition: isHorizontal ? "left" : "top",
        sourcePosition: isHorizontal ? "right" : "bottom",

        // Hardcode a width and height for elk to use when layouting.
        width: ["start", "end"].includes(type) ? 80 : 280,
        height: 80,
      };
    }),
    edges: edges,
  };

  return (
    elk
      // @ts-ignore
      .layout(graph)
      .then((layoutedGraph) => ({
        nodes: layoutedGraph?.children?.map((node) => ({
          ...node,
          // React Flow expects a position property on the node instead of `x`
          // and `y` fields.
          position: { x: node.x, y: node.y },
        })),

        edges: layoutedGraph.edges,
      }))
      .catch(console.error)
  );
};

const useWorkflowInitialization = (
  definition: ReactFlowDefinition,
  toolboxConfiguration: Record<string, any>
) => {
  const {
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
      const opts = { ...layoutOptions, "elk.direction": direction };
      const ns = useInitialNodes ? initialNodes : nodes;
      const es = useInitialNodes ? initialEdges : edges;

      // @ts-ignore
      getLayoutedElements(ns, es, opts).then(
        // @ts-ignore
        ({ nodes: layoutedNodes, edges: layoutedEdges }) => {
          layoutedEdges = layoutedEdges.map((edge: Edge) => {
            return {
              ...edge,
              animated: !!edge?.target?.includes("empty"),
              data: { ...edge.data, isLayouted: true },
            };
          });
          layoutedNodes.forEach((node: FlowNode) => {
            node.data = { ...node.data, isLayouted: true };
          });
          setNodes(layoutedNodes);
          setEdges(layoutedEdges);
          setIsLayouted(true);
          setFinalEdges(layoutedEdges);
          setFinalNodes(layoutedNodes);
        }
      );
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
    initializeWorkflow();
  }, []);

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
