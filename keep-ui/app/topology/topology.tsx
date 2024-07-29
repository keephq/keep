"use client";
import React, { useEffect, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  // MiniMap,
  Node,
  ReactFlow,
  ReactFlowInstance,
  ReactFlowProvider,
} from "@xyflow/react";
import dagre, { graphlib } from "@dagrejs/dagre";
import "@xyflow/react/dist/style.css";
import CustomNode from "./custom-node";
import { Card } from "@tremor/react";
import {
  edgeLabelBgPaddingNoHover,
  edgeLabelBgStyleNoHover,
  edgeLabelBgBorderRadiusNoHover,
  edgeMarkerEndNoHover,
  edgeLabelBgStyleHover,
  edgeMarkerEndHover,
  nodeHeight,
  nodeWidth,
} from "./styles";
import "./topology.css";
import { useTopology } from "utils/hooks/useTopology";
import Loading from "app/loading";

// Function to create a Dagre layout
const dagreGraph = new graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const getLayoutedElements = (nodes: any[], edges: any[]) => {
  dagreGraph.setGraph({ rankdir: "LR", nodesep: 50, ranksep: 200 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  nodes.forEach((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    node.targetPosition = "left";
    node.sourcePosition = "right";

    node.position = {
      x: nodeWithPosition.x - nodeWidth / 2,
      y: nodeWithPosition.y - nodeHeight / 2,
    };

    return node;
  });

  return { nodes, edges };
};

const TopologyPage = () => {
  // State for nodes and edges
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [reactFlowInstance, setReactFlowInstance] =
    useState<ReactFlowInstance<Node, Edge>>();

  const { topologyData, error, isLoading } = useTopology();

  const onEdgeHover = (eventType: "enter" | "leave", edge: Edge) => {
    const newEdges = [...edges];
    const currentEdge = newEdges.find((e) => e.id === edge.id);
    if (currentEdge) {
      currentEdge.style = eventType === "enter" ? { stroke: "orange" } : {};
      currentEdge.labelBgStyle =
        eventType === "enter" ? edgeLabelBgStyleHover : edgeLabelBgStyleNoHover;
      currentEdge.markerEnd =
        eventType === "enter" ? edgeMarkerEndHover : edgeMarkerEndNoHover;
      currentEdge.labelStyle = eventType === "enter" ? { fill: "white" } : {};
      setEdges(newEdges);
    }
  };

  const zoomToNode = (nodeId: string) => {
    const node = reactFlowInstance?.getNode(nodeId);
    if (node && reactFlowInstance) {
      reactFlowInstance.setCenter(node.position.x, node.position.y);
    }
  };

  useEffect(() => {
    if (!topologyData) return;

    // Create nodes from service definitions
    const newNodes = topologyData.map((service) => ({
      id: service.id.toString(),
      type: "customNode",
      data: service,
      position: { x: 0, y: 0 }, // Dagre will handle the actual position
    }));

    // Create edges from service dependencies
    const edgeMap = new Map<string, Edge>();

    topologyData.forEach((service) => {
      service.dependencies.forEach((dependency) => {
        const dependencyService = topologyData.find(
          (s) => s.id === dependency.serviceId
        );
        const edgeId = `${service.service}_${dependency.protocol}_${
          dependencyService
            ? dependencyService.service
            : dependency.serviceId.toString()
        }`;
        if (!edgeMap.has(edgeId)) {
          edgeMap.set(edgeId, {
            id: edgeId,
            source: service.id.toString(),
            target: dependency.serviceId.toString(),
            label: dependency.protocol === "unknown" ? "" : dependency.protocol,
            animated: true,
            labelBgPadding: edgeLabelBgPaddingNoHover,
            labelBgStyle: edgeLabelBgStyleNoHover,
            labelBgBorderRadius: edgeLabelBgBorderRadiusNoHover,
            markerEnd: edgeMarkerEndNoHover,
          });
        }
      });
    });

    const newEdges = Array.from(edgeMap.values());
    const layoutedElements = getLayoutedElements(newNodes, newEdges);
    setNodes(layoutedElements.nodes);
    setEdges(layoutedElements.edges);
  }, [topologyData]);

  if (isLoading || !topologyData) return <Loading />;
  if (error) return <div>Error loading topology data</div>;

  return (
    <Card className="p-4 md:p-10 mx-auto h-full">
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          snapToGrid
          fitViewOptions={{ padding: 0.2 }}
          onEdgeMouseEnter={(_event, edge) => onEdgeHover("enter", edge)}
          onEdgeMouseLeave={(_event, edge) => onEdgeHover("leave", edge)}
          nodeTypes={{ customNode: CustomNode }}
          onInit={(instance) => {
            setReactFlowInstance(instance);
          }}
        >
          <Background variant={BackgroundVariant.Lines} />
          {/* <MiniMap pannable zoomable /> */}
          <Controls />
        </ReactFlow>
      </ReactFlowProvider>
    </Card>
  );
};

export default TopologyPage;
