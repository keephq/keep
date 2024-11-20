"use client";
import React, {
  useCallback,
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
  FitViewOptions,
} from "@xyflow/react";
import { ServiceNode } from "./service-node";
import { Card, MultiSelect, MultiSelectItem } from "@tremor/react";
import { ArrowUpRightIcon } from "@heroicons/react/24/outline";
import {
  edgeLabelBgStyleNoHover,
  edgeMarkerEndNoHover,
  edgeLabelBgStyleHover,
  edgeMarkerEndHover,
} from "./styles";
import "./topology.css";
import Loading from "../../../loading";
import { EmptyStateCard, Link } from "@/components/ui";
import { useRouter } from "next/navigation";
import { useTopologySearchContext } from "../../TopologySearchContext";
import { ApplicationNode } from "./application-node";
import { ManageSelection } from "./manage-selection";
import {
  useTopology,
  useTopologyApplications,
  TopologyApplication,
  TopologyNode,
  TopologyService,
  TopologyServiceMinimal,
  TopologyApplicationMinimal,
} from "@/app/(keep)/topology/model";
import { TopologySearchAutocomplete } from "../TopologySearchAutocomplete";
import "@xyflow/react/dist/style.css";
import { areSetsEqual } from "@/utils/helpers";
import { getLayoutedElements } from "@/app/(keep)/topology/ui/map/getLayoutedElements";
import { getNodesAndEdgesFromTopologyData } from "@/app/(keep)/topology/ui/map/getNodesAndEdgesFromTopologyData";

const defaultFitViewOptions: FitViewOptions = {
  padding: 0.1,
  minZoom: 0.3,
};

type TopologyMapProps = {
  topologyServices?: TopologyService[];
  topologyApplications?: TopologyApplication[];
  providerIds?: string[];
  services?: string[];
  environment?: string;
  isVisible?: boolean;
  standalone?: boolean;
};

export function TopologyMap({
  topologyServices: initialTopologyServices,
  topologyApplications: initialTopologyApplications,
  providerIds,
  services,
  environment,
  isVisible = true,
  standalone = false,
}: TopologyMapProps) {
  const [initiallyFitted, setInitiallyFitted] = useState(false);

  const { topologyData, isLoading, error } = useTopology({
    providerIds,
    services,
    environment,
    initialData: initialTopologyServices,
  });
  const { applications } = useTopologyApplications({
    initialData: initialTopologyApplications,
  });
  const router = useRouter();

  const {
    selectedObjectId,
    setSelectedObjectId,
    selectedApplicationIds,
    setSelectedApplicationIds,
  } = useTopologySearchContext();

  const applicationMap = useMemo(() => {
    const map = new Map<string, TopologyApplication>();
    applications.forEach((app) => {
      map.set(app.id, app);
    });
    return map;
  }, [applications]);

  // State for nodes and edges
  const [nodes, setNodes] = useState<TopologyNode[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  const reactFlowInstanceRef = useRef<ReactFlowInstance<TopologyNode, Edge>>();

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
    // setTimeout is used to be sure that reactFlow will handle the fitView correctly
    setTimeout(() => {
      reactFlowInstanceRef.current?.fitView({
        padding: 0.2,
        nodes: nodesToFit,
        duration: 300,
        maxZoom: 1,
      });
    }, 0);
  }, []);

  const onNodesChange = useCallback((changes: NodeChange<TopologyNode>[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds));
  }, []);

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

  const handleSelectFromSearch = useCallback(
    ({
      value,
    }: {
      value: TopologyServiceMinimal | TopologyApplicationMinimal;
    }) => {
      if ("service" in value) {
        setSelectedObjectId(value.service);
      } else {
        const application = applicationMap.get(value.id);
        if (application) {
          setSelectedObjectId(application.id);
        }
      }
    },
    [applicationMap, setSelectedObjectId]
  );

  // if the topology is not visible on first load, we need to fit the view manually
  useEffect(
    function fallbackFitView() {
      if (!isVisible || initiallyFitted) return;
      setTimeout(() => {
        reactFlowInstanceRef.current?.fitView(defaultFitViewOptions);
      }, 0);
      setInitiallyFitted(true);
    },
    [isVisible, initiallyFitted]
  );

  useEffect(() => {
    if (!isVisible || !selectedObjectId || selectedObjectId === "") {
      return;
    }
    const node = reactFlowInstanceRef.current?.getNode(selectedObjectId);
    if (node) {
      highlightNodes([selectedObjectId]);
      fitViewToServices([selectedObjectId]);
      setSelectedObjectId(null);
      return;
    }
    const application = applicationMap.get(selectedObjectId);
    if (!application) {
      return;
    }
    const serviceIds = application.services.map((s) => s.service);
    highlightNodes(serviceIds);
    fitViewToServices(serviceIds);
    setSelectedObjectId(null);
  }, [
    isVisible,
    applicationMap,
    fitViewToServices,
    highlightNodes,
    selectedObjectId,
    setSelectedObjectId,
  ]);

  const previousNodesIds = useRef<Set<string>>(new Set());

  useEffect(
    function createAndSetLayoutedNodesAndEdges() {
      if (!topologyData) {
        return;
      }

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
        setEdges((prev) => prev.map((e) => ({ ...e, hidden: false })));
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
      // Hide all nodes and edges that are not part of selected applications
      setNodes((prev) =>
        prev.map((n) => {
          const isSelectedService = selectedServiceNodesIds.has(n.id);
          return {
            ...n,
            hidden: n.type === "service" && !isSelectedService,
          };
        })
      );
      setEdges((prev) =>
        prev.map((e) => {
          const isSelectedService =
            selectedServiceNodesIds.has(e.source) &&
            selectedServiceNodesIds.has(e.target);
          return {
            ...e,
            hidden: !isSelectedService,
          };
        })
      );

      const nodesToFit: TopologyNode[] = Array.from(
        selectedServiceNodesIds.values()
      )
        .map((id) => reactFlowInstanceRef.current?.getNode(id))
        .filter((node) => !!node);
      // Then fit view to selected nodes
      reactFlowInstanceRef.current?.fitView({
        padding: 10,
        minZoom: 0.5,
        nodes: nodesToFit,
        duration: 300,
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
    <div className="flex flex-col gap-4 h-full">
      <div className="flex justify-between items-baseline gap-4">
        <TopologySearchAutocomplete
          wrapperClassName="w-full flex-1"
          includeApplications={true}
          providerIds={providerIds}
          services={services}
          environment={environment}
          placeholder="Search for a service or application"
          onSelect={handleSelectFromSearch}
        />
        {/* Using z-index to overflow the manage selection component */}
        <div className="basis-1/3 relative z-30">
          <MultiSelect
            placeholder="Show application"
            value={selectedApplicationIds}
            onValueChange={setSelectedApplicationIds}
            disabled={!applications.length}
          >
            {applications.map((app) => (
              <MultiSelectItem key={app.id} value={app.id}>
                {app.name}
              </MultiSelectItem>
            ))}
          </MultiSelect>
        </div>
        {!standalone ? (
          <div>
            <Link
              icon={ArrowUpRightIcon}
              iconPosition="right"
              className="mr-2"
              href="/topology"
            >
              Full topology map
            </Link>
          </div>
        ) : null}
      </div>
      <Card className="p-0 h-full mx-auto relative overflow-hidden flex flex-col">
        <ReactFlowProvider>
          <ManageSelection />
          <ReactFlow
            nodes={nodes}
            edges={edges}
            minZoom={0.1}
            snapToGrid
            fitView
            fitViewOptions={defaultFitViewOptions}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            zoomOnDoubleClick={true}
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
    </div>
  );
}
