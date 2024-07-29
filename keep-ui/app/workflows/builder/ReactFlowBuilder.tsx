import React, {
  useCallback,
  useEffect,
  useState,
  useRef,
  useLayoutEffect,
} from "react";
import {
  applyEdgeChanges,
  applyNodeChanges,
  addEdge,
  Background,
  Controls,
  ReactFlow,
  Node,
  Edge,
  Connection,
} from "@xyflow/react";
import { parseWorkflow, generateWorkflow } from "./utils";
import { useSearchParams } from "next/navigation";
import { v4 as uuidv4 } from "uuid";
import "@xyflow/react/dist/style.css";
import CustomNode from "./CustomNode";
import CustomEdge from "./CustomEdge";
import { Provider } from "app/providers/providers";
import dagre from "dagre";

const nodeTypes = {
  custom: CustomNode,
  // subflow: SubFlowNode,
};

const edgeTypes = {
  "custom-edge": CustomEdge,
};

type CustomNode = Node & {
  prevStepId?: string;
  edge_label?: string;
};

const ReactFlowBuilder = ({
  workflow,
  loadedAlertFile,
  providers,
  toolboxConfiguration,
}: {
  workflow: string;
  loadedAlertFile: string;
  providers: Provider[];
  toolboxConfiguration?: Record<string, any>;
}) => {
  const [nodes, setNodes] = useState<CustomNode[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
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

  const onConnect = useCallback(
    (connection: Connection) => {
      const edge = { ...connection, type: "custom-edge" };
      setEdges((eds) => addEdge(edge, eds));
    },
    [setEdges]
  );

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

  const newEdgesFromNodes = (nodes: CustomNode[]): Edge[] => {
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
      let newEdges = newEdgesFromNodes(newNodes); // GENERATE EDGES BASED ON NODES

      const { nodes, edges } = getLayoutedElements(newNodes, newEdges);

      setNodes(nodes);
      setEdges(edges);
      setIsLoading(false);
    };

    initializeWorkflow();
  }, [
    loadedAlertFile,
    workflow,
    alertName,
    alertSource,
    providers,
    nodeDimensions,
  ]);

  const getLayoutedElements = (nodes: CustomNode[], edges: Edge[]) => {
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

    nodes.forEach((node) => {
      const nodeWithPosition = dagreGraph.node(node.id);
      node.targetPosition = "top";
      node.sourcePosition = "bottom";

      node.position = {
        x: nodeWithPosition.x - nodeDimensions.width / 2,
        y: nodeWithPosition.y - nodeDimensions.height / 2,
      };
    });

    return { nodes, edges };
  };

  const processWorkflow = (sequence: any, parentId?: string) => {
    let newNodes: CustomNode[] = [];

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
    let newNode: CustomNode;
    let newNodes: CustomNode[] = [];

    if (step.componentType === "switch") {
      const subflowId = uuidv4();
      newNode = {
        id: subflowId,
        type: "custom",
        position,
        data: {
          label: "Switch",
          type: "sub_flow",
        },
        style: {
          border: "2px solid orange",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
        },
        prevStepId: prevStepId,
        parentId: parentId,
      };
      if (parentId) {
        newNode.extent = "parent";
      }

      newNodes.push(newNode);

      const switchNode = {
        id: nodeId,
        type: "custom",
        position: { x: 0, y: 0 },
        data: {
          label: step.name,
          ...step,
        },
        parentId: subflowId,
        prevStepId: "",
        extent: "parent",
      } as CustomNode;

      newNodes.push(switchNode);

      const trueSubflowNodes: CustomNode[] = processWorkflow(
        step?.branches?.true,
        subflowId
      );
      const falseSubflowNodes: CustomNode[] = processWorkflow(
        step?.branches?.false,
        subflowId
      );

      if (trueSubflowNodes.length > 0) {
        trueSubflowNodes[0].edge_label = "True";
        trueSubflowNodes[0].prevStepId = nodeId; // CORRECT THE PREVIOUS STEP ID FOR THE TRUE BRANCH
      }

      if (falseSubflowNodes.length > 0) {
        falseSubflowNodes[0].edge_label = "False";
        falseSubflowNodes[0].prevStepId = nodeId; // CORRECT THE PREVIOUS STEP ID FOR THE FALSE BRANCH
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
        parentId: parentId,
        extent: parentId ? "parent" : "",
      } as CustomNode;

      newNodes.push(newNode);
    }

    return newNodes;
  };

  return (
    <div className="w-full h-full m-2">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={(changes) =>
          setNodes((nds) => applyNodeChanges(changes, nds))
        }
        onEdgesChange={(changes) =>
          setEdges((eds) => applyEdgeChanges(changes, eds))
        }
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
      >
        <Controls />
        <Background />
      </ReactFlow>
    </div>
  );
};

export default ReactFlowBuilder;
