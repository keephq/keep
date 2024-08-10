import {
  useEffect,
  useState,
  useRef,
  useCallback,
} from "react";
import { Edge, useReactFlow } from "@xyflow/react";
import dagre from "dagre";
import {
  parseWorkflow,
  generateWorkflow,
  buildAlert,
} from "app/workflows/builder/utils";
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
  "elk.direction": "BOTTOM",                          // Direction of layout
  "org.eclipse.elk.layered.layering.strategy": "INTERACTIVE", // Interactive layering strategy
  "org.eclipse.elk.edgeRouting": "ORTHOGONAL",       // Use orthogonal routing
  "elk.layered.unnecessaryBendpoints": "true",        // Allow bend points if necessary
  "elk.layered.spacing.edgeNodeBetweenLayers": "50",  // Spacing between edges and nodes
  "org.eclipse.elk.layered.nodePlacement.bk.fixedAlignment": "BALANCED", // Balanced node placement
  "org.eclipse.elk.layered.cycleBreaking.strategy": "DEPTH_FIRST", // Strategy for cycle breaking
  "elk.insideSelfLoops.activate": true,               // Handle self-loops inside nodes
  "separateConnectedComponents": "false",             // Do not separate connected components
  "spacing.componentComponent": "70",                 // Spacing between components
  "spacing": "75",                                    // General spacing
  "elk.spacing.nodeNodeBetweenLayers": "70",          // Spacing between nodes in different layers
  "elk.spacing.nodeNode": "8",                        // Spacing between nodes
  "elk.layered.spacing.nodeNodeBetweenLayers": "75",  // Spacing between nodes between layers
  "portConstraints": "FIXED_ORDER",                   // Fixed order for ports
  "nodeSize.constraints": "[MINIMUM_SIZE]",            // Minimum size constraints for nodes
  "elk.alignment": "CENTER",                          // Center alignment
  "elk.spacing.edgeNodeBetweenLayers": "50.0",        // Spacing between edges and nodes
  "org.eclipse.elk.layoutAncestors": "true",          // Layout ancestors
  "elk.edgeRouting": "ORTHOGONAL",                    // Ensure orthogonal edge routing
  "elk.layered.edgeRouting": "ORTHOGONAL",            // Ensure orthogonal edge routing in layered layout
  "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF", // Node placement strategy for symmetry
  "elk.layered.nodePlacement.outerSpacing": "20",    // Spacing around nodes to prevent overlap
  "elk.layered.nodePlacement.outerPadding": "20",    // Padding around nodes
  "elk.layered.edgeRouting.orthogonal": true
}

const getRandomColor = () => {
  const letters = '0123456789ABCDEF';
  let color = '#';
  for (let i = 0; i < 6; i++) {
    color += letters[Math.floor(Math.random() * 16)];
  }
  return color;
};

const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const getLayoutedElements = (nodes: FlowNode[], edges: Edge[], options = {}) => {
  const isHorizontal = options?.['elk.direction'] === 'RIGHT';
  const elk = new ELK();

  const graph = {
    id: 'root',
    layoutOptions: options,
    children: nodes.map((node) => {
      const type = node?.data?.type
        ?.replace("step-", "")
        ?.replace("action-", "")
        ?.replace("condition-", "")
        ?.replace("__end", "");
      return ({
        ...node,
        // Adjust the target and source handle positions based on the layout
        // direction.
        targetPosition: isHorizontal ? 'left' : 'top',
        sourcePosition: isHorizontal ? 'right' : 'bottom',

        // Hardcode a width and height for elk to use when layouting.
        width: ['start', 'end'].includes(type) ? 80 : 280,
        height: 80,
      })
    }),
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
    setIsLayouted,
    setLastSavedChanges,
    changes,
    setChanges,
    firstInitilisationDone,
    setFirstInitilisationDone
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
      if(!firstInitilisationDone){
        setFirstInitilisationDone(true)
        setLastSavedChanges({nodes: nodes, edges: edges});
        setChanges(0)
      }
    }

    if (!isLayouted && nodes.length === 0) {
      setIsLayouted(true);
      if(!firstInitilisationDone){
        setChanges(0)
      }
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