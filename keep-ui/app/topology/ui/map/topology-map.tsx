"use client";
import React, {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
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
import { Card, MultiSelect, MultiSelectItem } from "@tremor/react";
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
import Loading from "../../../loading";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { useRouter, useSearchParams } from "next/navigation";
import { ServiceSearchContext } from "../../service-search-context";
import {
  TopologyApplication,
  ServiceNodeType,
  TopologyNode,
  TopologyService,
  TopologyServiceMinimal,
  TopologyApplicationMinimal,
} from "../../models";
import { ApplicationNode } from "./application-node";
import { useTopologyApplications } from "../../../../utils/hooks/useApplications";
import { ManageSelection } from "./manage-selection";
import { useTopology } from "../../../../utils/hooks/useTopology";
import { TopologySearchAutocomplete } from "../TopologySearchAutocomplete";

function areSetsEqual<T>(set1: Set<T>, set2: Set<T>): boolean {
  if (set1.size !== set2.size) {
    return false;
  }

  for (const item of set1) {
    if (!set2.has(item)) {
      return false;
    }
  }

  return true;
}

const getLayoutedElements = (nodes: TopologyNode[], edges: Edge[]) => {
  const dagreGraph = new graphlib.Graph({});

  // Function to create a Dagre layout
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({
    rankdir: "LR",
    nodesep: 50,
    ranksep: 200,
  });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  nodes.forEach((node) => {
    const gNode = dagreGraph.node(node.id);
    // if (!node.parentId) {
    node.position = {
      x: gNode.x - gNode.width / 2,
      y: gNode.y - gNode.height / 2,
    };
    node.style = {
      ...node.style,
      width: gNode.width as number,
      height: gNode.height as number,
    };
    node.targetPosition = Position.Left;
    node.sourcePosition = Position.Right;
  });

  return { nodes, edges };
};

function getNodesAndEdgesFromTopologyData(
  topologyData: TopologyService[],
  applicationsMap: Map<string, TopologyApplication>
) {
  const nodeMap = new Map<string, TopologyNode>();
  const edgeMap = new Map<string, Edge>();
  // Create nodes from service definitions
  for (const service of topologyData) {
    const node: ServiceNodeType = {
      id: service.service.toString(),
      type: "service",
      data: service,
      position: { x: 0, y: 0 }, // Dagre will handle the actual positioning
      selectable: true,
    };
    if (service.application_ids.length > 0) {
      node.data.applications = service.application_ids
        .map((id) => {
          const app = applicationsMap.get(id);
          if (!app) {
            return null;
          }
          return {
            id: app.id,
            name: app.name,
          };
        })
        .filter((a) => !!a);
    }
    nodeMap.set(service.service.toString(), node);
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
  }

  return { nodeMap, edgeMap };
}

export function TopologyMap({
  topologyServices: initialTopologyServices,
  topologyApplications: initialTopologyApplications,
  providerId: providerIdProp,
  service: serviceProp,
  environment: environmentProp,
}: {
  topologyServices?: TopologyService[];
  topologyApplications?: TopologyApplication[];
  providerId?: string;
  service?: string;
  environment?: string;
}) {
  console.log("render topology map");
  const params = useSearchParams();
  const providerId = providerIdProp || params?.get("providerId") || undefined;
  const service = serviceProp || params?.get("service") || undefined;
  const environment =
    environmentProp || params?.get("environment") || undefined;

  const { topologyData, isLoading, error } = useTopology({
    providerId,
    service,
    environment,
    initialData: initialTopologyServices,
  });
  const { applications } = useTopologyApplications({
    initialData: initialTopologyApplications,
  });
  const router = useRouter();

  const [selectedApplicationIds, setSelectedApplicationIds] = useState<
    string[]
  >([]);
  // State for nodes and edges
  const [nodes, setNodes] = useState<TopologyNode[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const { selectedServiceId, setSelectedServiceId } =
    useContext(ServiceSearchContext);
  const applicationMap = useMemo(() => {
    const map = new Map<string, TopologyApplication>();
    applications.forEach((app) => {
      map.set(app.id, app);
    });
    return map;
  }, [applications]);

  const reactFlowInstanceRef = useRef<ReactFlowInstance<TopologyNode, Edge>>();

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

  const highlightNodes = useCallback((nodeIds: string[]) => {
    setNodes((nds) =>
      nds.map((n) => {
        return {
          ...n,
          selected: nodeIds.includes(n.id),
        };
      })
    );
  }, []);

  const fitViewToServices = useCallback((serviceIds: string[]) => {
    const nodesToFit: TopologyNode[] = [];
    for (const id of serviceIds) {
      const node = reactFlowInstanceRef.current?.getNode(id);
      if (node) {
        nodesToFit.push(node);
      }
    }
    reactFlowInstanceRef.current?.fitView({
      padding: 10,
      minZoom: 0.5,
      nodes: nodesToFit,
      duration: 300,
    });
  }, []);

  const handleSelectFromSearch = useCallback(
    ({
      value,
    }: {
      value: TopologyServiceMinimal | TopologyApplicationMinimal;
    }) => {
      if ("service" in value) {
        setSelectedServiceId(value.service);
      } else {
        const application = applicationMap.get(value.id);
        if (application) {
          setSelectedServiceId(application.id);
        }
      }
    },
    [applicationMap, setSelectedServiceId]
  );

  useEffect(() => {
    if (!selectedServiceId || selectedServiceId === "") {
      return;
    }
    const node = reactFlowInstanceRef.current?.getNode(selectedServiceId);
    if (node) {
      fitViewToServices([selectedServiceId]);
      highlightNodes([selectedServiceId]);
      setSelectedServiceId(null);
      return;
    }
    const application = applicationMap.get(selectedServiceId);
    if (!application) {
      return;
    }
    const serviceIds = application.services.map((s) => s.service);
    fitViewToServices(serviceIds);
    highlightNodes(serviceIds);
    setSelectedServiceId(null);
  }, [
    applicationMap,
    fitViewToServices,
    highlightNodes,
    selectedServiceId,
    setSelectedServiceId,
  ]);

  const previousNodesIds = useRef<Set<string>>(new Set());

  useEffect(
    function createAndSetLayoutedNodesAndEdges() {
      if (!topologyData) return;

      const { nodeMap, edgeMap } = getNodesAndEdgesFromTopologyData(
        topologyData,
        applicationMap
      );

      const newNodes = Array.from(nodeMap.values());
      const newEdges = Array.from(edgeMap.values());

      if (
        previousNodesIds.current.size > 0 &&
        areSetsEqual(previousNodesIds.current, new Set(nodeMap.keys()))
      ) {
        setEdges(newEdges);
        setNodes((prevNodes) =>
          prevNodes.map((n) => {
            const newNode = newNodes.find((nn) => nn.id === n.id);
            if (newNode) {
              // Update node, but keep the position
              return { ...newNode, position: n.position };
            }
            return n;
          })
        );
      } else {
        previousNodesIds.current = new Set(nodeMap.keys());
      }

      const layoutedElements = getLayoutedElements(newNodes, newEdges);

      // Adjust group node sizes and positions
      setNodes(layoutedElements.nodes);
      setEdges(layoutedElements.edges);
    },
    [topologyData, applicationMap]
  );

  useEffect(
    function watchSelectedApplications() {
      if (selectedApplicationIds.length === 0) {
        setNodes((prev) => prev.map((n) => ({ ...n, hidden: false })));
        return;
      }
      // Get all service nodes that are part of selected applications
      const selectedServiceNodesIds = new Set(
        applications.flatMap((app) =>
          selectedApplicationIds.includes(app.id)
            ? app.services.map((s) => s.service.toString())
            : []
        )
      );
      // Hide all nodes that are not part of selected applications
      setNodes((prev) => {
        const selectedNodes: TopologyNode[] = [];
        const newNodes = prev.map((n) => {
          const isSelectedService = selectedServiceNodesIds.has(n.id);
          if (n.type === "service" && isSelectedService) {
            selectedNodes.push(n);
          }
          return {
            ...n,
            hidden: n.type === "service" && !isSelectedService,
          };
        });
        // Fit view to selected nodes
        // TODO: handle case when nodes are two far apart and minZoom preventing fitView
        reactFlowInstanceRef.current?.fitView({
          padding: 10,
          minZoom: 0.5,
          nodes: selectedNodes,
          duration: 300,
        });
        return newNodes;
      });
    },
    [applications, selectedApplicationIds]
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
    <>
      <div className="flex justify-between gap-4 mb-4">
        <TopologySearchAutocomplete
          wrapperClassName="w-full flex-1"
          includeApplications={true}
          providerId={providerId}
          service={service}
          environment={environment}
          placeholder="Search for a service or application"
          onSelect={handleSelectFromSearch}
        />
        {/* Using z-index to overflow the manage selection component */}
        <div className="basis-1/3 relative z-30">
          <MultiSelect
            placeholder="Show application"
            onValueChange={setSelectedApplicationIds}
          >
            {applications.map((app) => (
              <MultiSelectItem key={app.id} value={app.id}>
                {app.name}
              </MultiSelectItem>
            ))}
          </MultiSelect>
        </div>
      </div>
      <Card className="p-0 mx-auto h-full my-4 relative overflow-hidden flex flex-col">
        <ReactFlowProvider>
          <ManageSelection />
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
              service: ServiceNode,
              application: ApplicationNode,
            }}
            onInit={(instance) => {
              reactFlowInstanceRef.current = instance;
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
    </>
  );
}
