import { useEffect, useState, useLayoutEffect, useRef, useCallback } from "react";
import { Connection, Edge, Node, Position, useReactFlow } from "@xyflow/react";
import dagre from "dagre";
import { parseWorkflow, generateWorkflow } from "app/workflows/builder/utils";
import { v4 as uuidv4 } from "uuid";
import { useSearchParams } from "next/navigation";
import useStore from "../../app/workflows/builder/builder-store";
import { FlowNode } from "../../app/workflows/builder/builder-store";

const useWorkflowInitialization = (
  workflow: string,
  loadedAlertFile: string,
  providers: any[]
) => {
  const { nodes, edges, setNodes, setEdges, onNodesChange, onEdgesChange, onConnect, onDragOver, onDrop } = useStore();

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

  const handleDrop = useCallback(
    (event) => {
      onDrop(event, screenToFlowPosition);
    },
    [screenToFlowPosition]
  );

  

  const newEdgesFromNodes = (nodes: FlowNode[]): Edge[] => {
    const edges: Edge[] = [];

    nodes.forEach((node) => {
      if (node.prevStepId) {
        edges.push({
          id: `e${node.prevStepId}-${node.id}`,
          source: node.prevStepId,
          target: node.id,
          type: "custom-edge",
          label: node.edge_label || "",
        });
      }
    });
    return edges;
  };

  useLayoutEffect(() => {
    if (nodeRef.current) {
      const { width, height } = nodeRef.current.getBoundingClientRect();
      setNodeDimensions({ width: width + 20, height: height + 20 });
    }
  }, [nodes.length]);

  useEffect(() => {
    const alertNameParam = searchParams?.get("alertName");
    const alertSourceParam = searchParams?.get("alertSource");
    setAlertName(alertNameParam);
    setAlertSource(alertSourceParam);
  }, [searchParams]);

  useEffect(() => {
    const initializeWorkflow = async () => {
      setIsLoading(true);
      let parsedWorkflow;

      if (workflow) {
        parsedWorkflow = parseWorkflow(workflow, providers);
      } else if (loadedAlertFile == null) {
        const alertUuid = uuidv4();
        let triggers = {};
        if (alertName && alertSource) {
          triggers = { alert: { source: alertSource, name: alertName } };
        }
        parsedWorkflow = generateWorkflow(alertUuid, "", "", [], [], triggers);
      } else {
        parsedWorkflow = parseWorkflow(loadedAlertFile, providers);
      }
      
      let newNodes = processWorkflow(parsedWorkflow.sequence);
      let newEdges = newEdgesFromNodes(newNodes);

      const { nodes, edges } = getLayoutedElements(newNodes, newEdges);

      setNodes(nodes);
      setEdges(edges);
      setIsLoading(false);
    };

    initializeWorkflow();
  }, [loadedAlertFile, workflow, alertName, alertSource, providers]);

  const getLayoutedElements = (nodes: FlowNode[], edges: Edge[]) => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));

    dagreGraph.setGraph({ rankdir: "TB", nodesep: 100, edgesep: 100 });

    nodes.forEach((node) => {
      dagreGraph.setNode(node.id, {
        width: nodeDimensions.width,
        height: nodeDimensions.height,
      });
    });

    edges.forEach((edge) => {
      dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    nodes.forEach((node: FlowNode) => {
      const nodeWithPosition = dagreGraph.node(node.id);
      node.targetPosition = "top" as Position; 
      node.sourcePosition = "bottom" as Position;

      node.position = {
        x: nodeWithPosition.x - nodeDimensions.width / 2,
        y: nodeWithPosition.y - nodeDimensions.height / 2,
      };
    });

    return { nodes, edges };
  };

  const processWorkflow = (sequence: any, parentId?: string) => {
    let newNodes: FlowNode[] = [];

    sequence.forEach((step: any, index: number) => {
      const newPrevStepId = sequence?.[index - 1]?.id || "";
      const nodes = processStep(
        step,
        { x: index * 200, y: 50 },
        newPrevStepId,
        parentId
      );
      newNodes = [...newNodes, ...nodes];
    });

    return newNodes;
  };

  const processStep = (
    step: any,
    position: { x: number; y: number },
    prevStepId?: string,
    parentId?: string
  ) => {
    const nodeId = step.id;
    let newNode: FlowNode;
    let newNodes: FlowNode[] = [];

    if (step.componentType === "switch") {
      const subflowId = uuidv4();
    //   newNode = {
    //     id: subflowId,
    //     type: "custom",
    //     position,
    //     data: {
    //       label: "Switch",
    //       type: "sub_flow",
    //     },
    //     style: {
    //       border: "2px solid orange",
    //       width: "100%",
    //       height: "100%",
    //       display: "flex",
    //       flexDirection: "column",
    //       justifyContent: "space-between",
    //     },
    //     prevStepId: prevStepId,
    //     parentId: parentId,
    //   };
    //   if (parentId) {
    //     newNode.extent = "parent";
    //   }

      // newNodes.push(newNode);

      const switchNode = {
        id: nodeId,
        type: "custom",
        position: { x: 0, y: 0 },
        data: {
          label: step.name,
          ...step,
        },
        prevStepId: prevStepId,
        // extent: 'parent',
      } as FlowNode;

      newNodes.push(switchNode);

      // const trueSubflowNodes: FlowNode[] = processWorkflow(step?.branches?.true, subflowId);
      const trueSubflowNodes: FlowNode[] = processWorkflow(
        step?.branches?.true
      );
      // const falseSubflowNodes: FlowNode[] = processWorkflow(step?.branches?.false, subflowId);
      const falseSubflowNodes: FlowNode[] = processWorkflow(
        step?.branches?.false
      );

      if (trueSubflowNodes.length > 0) {
        trueSubflowNodes[0].edge_label = "True";
        trueSubflowNodes[0].prevStepId = nodeId;
      }

      if (falseSubflowNodes.length > 0) {
        falseSubflowNodes[0].edge_label = "False";
        falseSubflowNodes[0].prevStepId = nodeId;
      }

      newNodes = [...newNodes, ...trueSubflowNodes, ...falseSubflowNodes];
    } else {
      newNode = {
        id: nodeId,
        type: "custom",
        position,
        data: {
          label: step.name,
          ...step,
        },
        prevStepId: prevStepId,
        // parentId: parentId,
      } as FlowNode;

      newNodes.push(newNode);
    }

    return newNodes;
  };

  return {
    nodes,
    edges,
    isLoading,
    onNodesChange: onNodesChange,
    onEdgesChange: onEdgesChange,
    onConnect: onConnect,
    onDragOver: onDragOver,
    onDrop: handleDrop,

  };
};

export default useWorkflowInitialization;
