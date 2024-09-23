"use client";
import React, { useCallback, useContext, useEffect, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Node,
  Edge,
  ReactFlow,
  ReactFlowInstance,
  ReactFlowProvider,
  applyNodeChanges,
  applyEdgeChanges,
  NodeChange,
  EdgeChange,
  Position,
} from "@xyflow/react";
import dagre, { graphlib } from "@dagrejs/dagre";
import "@xyflow/react/dist/style.css";
import { ServiceNode } from "./service-node";
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
import Loading from "app/loading";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { useRouter } from "next/navigation";
import { ServiceSearchContext } from "../../service-search-context";
import { Application, ServiceNodeType } from "../../models";
import { ApplicationNode } from "./application-node";
import { CreateApplicationForm } from "../create-application-form";
import { ManageApplicationForm } from "../manage-application-form";
import { TopologyService } from "../../models";

const getLayoutedElements = (
  nodes: (ServiceNodeType | Node)[],
  edges: Edge[]
) => {
  // Function to create a Dagre layout
  const dagreGraph = new graphlib.Graph({ compound: true });
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({ rankdir: "LR", nodesep: 50, ranksep: 200 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
    if (node.parentId) {
      dagreGraph.setParent(node.id, node.parentId);
    }
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  nodes.forEach((node) => {
    const gNode = dagreGraph.node(node.id);
    const padding = 20;
    if (!node.parentId) {
      node.position = {
        x: gNode.x - gNode.width / 2 - padding,
        y: gNode.y - gNode.height / 2 - padding,
      };
      node.style = {
        // ...node.style,
        width: gNode.width + padding,
        height: gNode.height + padding,
      };
    } else {
      // For some reason, react flow adds the parent's x position to the child's x position
      // This is a fix to counteract that
      const parent = nodes.find((n) => n.id === node.parentId);
      const parentX = parent?.position.x || 0;
      const parentY = parent?.position.y || 0;
      node.position = {
        x: gNode.x - gNode.width / 2 - parentX,
        y: gNode.y - gNode.height / 2 - parentY,
      };
    }
    node.targetPosition = Position.Left;
    node.sourcePosition = Position.Right;
  });

  return { nodes, edges };
};

type TopologyNode = ServiceNodeType | Node;

export function TopologyMap({
  topologyData,
  isLoading,
  error,
}: {
  topologyData: TopologyService[] | undefined;
  isLoading: boolean;
  error: string;
}) {
  const router = useRouter();
  // State for nodes and edges
  const [nodes, setNodes] = useState<TopologyNode[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const { selectedServiceId, setSelectedServiceId } =
    useContext(ServiceSearchContext);
  const [reactFlowInstance, setReactFlowInstance] =
    useState<ReactFlowInstance<TopologyNode, Edge>>();

  const onNodesChange = useCallback(
    (changes: NodeChange<TopologyNode>[]) =>
      setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );
  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) =>
      setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
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
      let node = reactFlowInstance?.getNode(nodeId);
      if (!node) {
        // Maybe its by display name?
        node = reactFlowInstance
          ?.getNodes()
          .find((n) => n.data.display_name === nodeId);
      }
      if (!node || !reactFlowInstance) {
        console.log("Node not found", nodeId);
        return;
      }
      const { width = 0, height = 0 } = node.style || {};
      reactFlowInstance.setCenter(
        node.position.x + (width as number) / 2,
        node.position.y + (height as number) / 2,
        {
          duration: 300,
          zoom: 0.8,
          // zoom: Math.min(reactFlowInstance.getZoom() * 2, 1),
        }
      );
      // reactFlowInstance.fitBounds(
      //   {
      //     x: node.position.x,
      //     y: node.position.y,
      //     width: width as number,
      //     height: height as number,
      //   },
      //   {
      //     duration: 300,
      //   }
      // );
    },
    [reactFlowInstance]
  );

  useEffect(() => {
    if (selectedServiceId && selectedServiceId !== "") {
      zoomToNode(selectedServiceId);
      setSelectedServiceId(null);
      // select the node
      setNodes((nodes) =>
        nodes.map((node) => {
          return node.id === selectedServiceId
            ? { ...node, selected: true }
            : { ...node, selected: false };
        })
      );
    }
  }, [selectedServiceId, zoomToNode]);

  const createApplicationNode = (application: Application) => {
    return {
      id: application.name,
      type: "application",
      data: {
        label: application.name,
      },
      position: { x: 0, y: 0 },
    } as Node;
  };

  useEffect(
    function createAndSetLayoutedNodesAndEdges() {
      if (!topologyData) return;

      const newNodes: (ServiceNodeType | Node)[] = [];

      const createdApplications = new Map<string, boolean>();

      // Create nodes from service definitions
      topologyData.forEach((service) => {
        const node: ServiceNodeType = {
          id: service.service.toString(),
          type: "service",
          data: service,
          position: { x: 0, y: 0 }, // Dagre will handle the actual positioning
          selectable: true,
        };
        if (service.applicationObject) {
          node.parentId = service.applicationObject.name;
          node.extent = "parent";
          if (!createdApplications.has(service.applicationObject.name)) {
            newNodes.push(createApplicationNode(service.applicationObject));
            createdApplications.set(service.applicationObject.name, true);
          }
        }
        newNodes.push(node);
      });

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
              label:
                dependency.protocol === "unknown" ? "" : dependency.protocol,
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
    },
    [JSON.stringify(topologyData)]
  );

  if (isLoading) {
    return <Loading />;
  }
  if (error) {
    return (
      <div className="flex flex-col justify-center">
        <EmptyStateCard
          className="mt-20"
          title="Error Loading Topology Data"
          description="Seems like we encountred some problem while trying to load your topology data, please contact us if this issue continues"
          buttonText="Slack Us"
          onClick={() => {
            window.open("https://slack.keephq.dev/", "_blank");
          }}
        />
      </div>
    );
  }

  return (
    <Card className="p-0 mx-auto h-full my-4 relative overflow-hidden">
      <ReactFlowProvider>
        <CreateApplicationForm zoomToNode={zoomToNode} />
        <ManageApplicationForm zoomToNode={zoomToNode} />
        <ReactFlow
          nodes={nodes}
          edges={edges}
          minZoom={0.1}
          defaultViewport={{ x: 0, y: 0, zoom: 0.5 }}
          // fitView
          snapToGrid
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitViewOptions={{ padding: 0.3 }}
          zoomOnDoubleClick={true}
          // TODO: Change z-index of node on hover for details to overlay underlying node
          onEdgeMouseEnter={(_event, edge) => onEdgeHover("enter", edge)}
          onEdgeMouseLeave={(_event, edge) => onEdgeHover("leave", edge)}
          nodeTypes={{
            // TODO: fix type
            // @ts-ignore
            service: ServiceNode,
            application: ApplicationNode,
          }}
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
            <div className="absolute top-0 right-0 h-full w-full p-4 md:p-10">
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
}
