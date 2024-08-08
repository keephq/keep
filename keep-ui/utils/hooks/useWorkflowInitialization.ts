import {
  useEffect,
  useState,
  useRef,
  useCallback,
} from "react";
import { Edge, EdgeProps, MarkerType, Position, useReactFlow } from "@xyflow/react";
import dagre from "dagre";
import {
  parseWorkflow,
  generateWorkflow,
  buildAlert,
} from "app/workflows/builder/utils";
import { v4 as uuidv4 } from "uuid";
import { useSearchParams } from "next/navigation";
import useStore from "../../app/workflows/builder/builder-store";
import { FlowNode } from "../../app/workflows/builder/builder-store";
import { Provider } from "app/providers/providers";
import { Definition, Step } from "sequential-workflow-designer";
import { WrappedDefinition } from "sequential-workflow-designer-react";
import ELK from 'elkjs/lib/elk.bundled.js';
import { processWorkflowV2 } from "utils/reactFlow";
// import "@xyflow/react/dist/style.css";

const layoutOptions = {
  "elk.nodeLabels.placement": "INSIDE V_CENTER H_BOTTOM",
  "elk.algorithm": "layered",
  "elk.direction": "BOTTOM",
  "org.eclipse.elk.layered.layering.strategy": "INTRACTIVE",
  "org.eclipse.elk.edgeRouting": "ORTHOGONAL",
  "elk.layered.unnecessaryBendpoints": "true",
  "elk.layered.spacing.edgeNodeBetweenLayers": "50",
  "org.eclipse.elk.layered.nodePlacement.bk.fixedAlignment": "BALANCED",
  "org.eclipse.elk.layered.cycleBreaking.strategy": "DEPTH_FIRST",
  "org.eclipse.elk.insideSelfLoops.activate": true,
  "separateConnectedComponents": "false",
  "spacing.componentComponent": "70",
  "spacing": "75",
  "elk.spacing.nodeNodeBetweenLayers": "70",
  "elk.spacing.nodeNode": "8",
  "elk.layered.spacing.nodeNodeBetweenLayers": "75",
  "portConstraints": "FIXED_ORDER",
  "nodeSize.constraints": "[MINIMUM_SIZE]",
  "elk.alignment": "CENTER",
  "elk.spacing.edgeNodeBetweenLayers": "50.0",
  "org.eclipse.elk.layoutAncestors": "true",
}


const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const getLayoutedElements = (nodes: FlowNode[], edges: Edge[], options = {}) => {
  const isHorizontal = options?.['elk.direction'] === 'RIGHT';
  const elk = new ELK();

  const graph = {
    id: 'root',
    layoutOptions: options,
    children: nodes.map((node) => ({
      ...node,
      // Adjust the target and source handle positions based on the layout
      // direction.
      targetPosition: isHorizontal ? 'left' : 'top',
      sourcePosition: isHorizontal ? 'right' : 'bottom',

      // Hardcode a width and height for elk to use when layouting.
      width: 250,
      height: 80,
    })),
    edges: edges,
  };

  return elk
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
    .catch(console.error);
};


const useWorkflowInitialization = (
  workflow: string | undefined,
  loadedAlertFile: string | null | undefined,
  providers: Provider[],
  definition: WrappedDefinition<Definition>,
  onDefinitionChange: (def: WrappedDefinition<Definition>) => void,
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
    setIsLayouted
  } = useStore();

  const [isLoading, setIsLoading] = useState(true);
  const [alertName, setAlertName] = useState<string | null | undefined>(null);
  const [alertSource, setAlertSource] = useState<string | null | undefined>(
    null
  );
  const searchParams = useSearchParams();
  const nodeRef = useRef<HTMLDivElement | null>(null);
  const [nodeDimensions, setNodeDimensions] = useState({
    width: 200,
    height: 100,
  });
  const { screenToFlowPosition } = useReactFlow();
  // const [isLayouted, setIsLayouted] = useState(false);
  const { fitView } = useReactFlow();
  const definitionRef = useRef<Definition>(null);

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      onDrop(event, screenToFlowPosition);
    },
    [screenToFlowPosition]
  );

  const onLayout = useCallback(
    ({ direction, useInitialNodes = false, initialNodes, initialEdges }: {
      direction: string;
      useInitialNodes?: boolean;
      initialNodes?: FlowNode[],
      initialEdges?: Edge[]
    }) => {
      const opts = { ...layoutOptions, 'elk.direction': direction };
      const ns = useInitialNodes ? initialNodes : nodes;
      const es = useInitialNodes ? initialEdges : edges;

      // @ts-ignore
      getLayoutedElements(ns, es, opts).then(
        // @ts-ignore
        ({ nodes: layoutedNodes, edges: layoutedEdges }) => {
          layoutedEdges = layoutedEdges.map((edge: Edge) => {
            return {
              ...edge,
              animated: !!edge?.target?.includes('empty'),
              data: { ...edge.data, isLayouted: true }
            };
          })
          layoutedNodes.forEach((node: FlowNode) => {
            node.data = { ...node.data, isLayouted: true }
          })
          setNodes(layoutedNodes);
          setEdges(layoutedEdges);

          window.requestAnimationFrame(() => fitView());
        },
      );
    },
    [nodes, edges],
  );

  useEffect(() => {
    if (!isLayouted && nodes.length > 0) {
      onLayout({ direction: 'DOWN' })
      setIsLayouted(true)
    }

    if (!isLayouted && nodes.length === 0) {
      setIsLayouted(true);
    }
    // window.requestAnimationFrame(() => {
    //   fitView();
    // });
  }, [nodes, edges])



  const handleSpecialTools = (
    nodes: FlowNode[],
    toolMeta: {
      type: string;
      specialToolNodeId: string;
      switchCondition?: string;
    }
  ) => {
    if (!nodes) {
      return;
    }
  }

  useEffect(() => {
    const alertNameParam = searchParams?.get("alertName");
    const alertSourceParam = searchParams?.get("alertSource");
    setAlertName(alertNameParam);
    setAlertSource(alertSourceParam);
  }, [searchParams]);

  useEffect(() => {
    const initializeWorkflow = async () => {
      setIsLoading(true);
      let parsedWorkflow = definition?.value;
      console.log("parsedWorkflow", parsedWorkflow);
      setV2Properties(parsedWorkflow?.properties ?? {});
      // let { nodes: newNodes, edges: newEdges } = processWorkflow(
      //   parsedWorkflow?.sequence
      // );
      const sequences = [
        {
          id: "start",
          type: "start",
          componentType: "start",
          properties: {},
          isLayouted: false,
        } as Partial<Step>,
        ...(parsedWorkflow?.sequence || []),
        {
          id: "end",
          type: "end",
          componentType: "end",
          properties: {},
          isLayouted: false,
        } as Partial<Step>,
      ];
      const intialPositon = { x: 0, y: 50 };
      let { nodes, edges } = processWorkflowV2(sequences, intialPositon, true);
      console.log(nodes, edges);
      console.log("nodes", nodes);
      console.log("edges", edges);
      setIsLayouted(false);
      setNodes(nodes);
      setEdges(edges);
      setToolBoxConfig(toolboxConfiguration);
      setIsLoading(false);
    };
    initializeWorkflow();
  }, [
    loadedAlertFile,
    workflow,
    alertName,
    alertSource,
    providers,
    definition?.value,
  ]);


  return {
    nodes,
    edges,
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

