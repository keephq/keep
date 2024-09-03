"use client";
import React, { useCallback, useEffect, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  Node,
  ReactFlow,
  ReactFlowInstance,
  ReactFlowProvider,
} from "@xyflow/react";
import dagre, { graphlib } from "@dagrejs/dagre";
import "@xyflow/react/dist/style.css";
import CustomNode from "./custom-node";
import { Card, TextInput } from "@tremor/react";
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
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { useRouter } from "next/navigation";

interface Props {
  providerId?: string;
  service?: string;
  environment?: string;
  showSearch?: boolean;
}

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

const TopologyPage = ({
  providerId,
  service,
  environment,
  showSearch = true,
}: Props) => {
  const router = useRouter();
  // State for nodes and edges
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [serviceInput, setServiceInput] = useState<string>("");
  const [reactFlowInstance, setReactFlowInstance] =
    useState<ReactFlowInstance<Node, Edge>>();

  const { topologyData, error, isLoading } = useTopology(
    providerId,
    service,
    environment
  );

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

  const zoomToNode = useCallback(
    (nodeId: string) => {
      const node = reactFlowInstance?.getNode(nodeId);
      if (node && reactFlowInstance) {
        reactFlowInstance.setCenter(node.position.x, node.position.y);
      }
    },
    [reactFlowInstance]
  );

  useEffect(() => {
    if (serviceInput) {
      zoomToNode(serviceInput);
    }
  }, [serviceInput, zoomToNode]);

  useEffect(() => {
    if (!topologyData) return;

    // Create nodes from service definitions
    const newNodes = topologyData.map((service) => ({
      id: service.service.toString(),
      type: "customNode",
      data: service,
      position: { x: 0, y: 0 }, // Dagre will handle the actual positioning
    }));

    // Create edges from service dependencies
    const edgeMap = new Map<string, Edge>();

    topologyData.forEach((service) => {
      service.dependencies.forEach((dependency) => {
        const dependencyService = topologyData.find(
          (s) => s.service === dependency.serviceName
        );
        const edgeId = `${service.service}_${dependency.protocol}_${
          dependencyService
            ? dependencyService.service
            : dependency.serviceId.toString()
        }`;
        if (!edgeMap.has(edgeId)) {
          edgeMap.set(edgeId, {
            id: edgeId,
            source: service.service.toString(),
            target: dependency.serviceName.toString(),
            label: dependency.protocol === "unknown" ? "" : dependency.protocol,
            animated: false,
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

  if (isLoading) return <Loading />;
  if (error)
    return (
      <div className="flex flex-col justify-center">
        <EmptyStateCard
          className="mb-20"
          title="Error Loading Topology Data"
          description="Seems like we encountred some problem while trying to load your topology data, please contact us if this issue continues"
          buttonText="Slack Us"
          onClick={() => {
            window.open("https://slack.keephq.dev/", "_blank");
          }}
        />
      </div>
    );

  return (
    <Card className="p-4 md:p-10 mx-auto h-full relative mb-10">
      {showSearch && (
        <div className="flex justify-end items-center w-full absolute top-0 left-0">
          <TextInput
            placeholder="Search for a service"
            value={serviceInput}
            onValueChange={setServiceInput}
            className="w-96 mr-9 mt-2"
          />
        </div>
      )}
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          snapToGrid
          fitViewOptions={{ padding: 0.3 }}
          onEdgeMouseEnter={(_event, edge) => onEdgeHover("enter", edge)}
          onEdgeMouseLeave={(_event, edge) => onEdgeHover("leave", edge)}
          nodeTypes={{ customNode: CustomNode }}
          onInit={(instance) => {
            setReactFlowInstance(instance);
          }}
        >
          <Background variant={BackgroundVariant.Lines} />
          <Controls />
        </ReactFlow>
      </ReactFlowProvider>
      {!topologyData ||
        (topologyData?.length === 0 && (
          <>
            <div className="absolute top-0 right-0 bg-gray-200 opacity-30 h-full w-full" />
            <div className="absolute top-0 right-0 h-full w-full">
              <div className="relative w-full h-full flex flex-col justify-center mb-20">
                <EmptyStateCard
                  className="mb-20"
                  title="No Topology Available"
                  description="Seems like no topology data is available, start by connecting providers that support topology."
                  buttonText="Connect Providers"
                  onClick={() => router.push("/providers?labels=topology")}
                />
              </div>
            </div>
          </>
        ))}
    </Card>
  );
};

export default TopologyPage;
