"use client";
import React, {
  ElementType,
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
  addEdge,
  reconnectEdge,
} from "@xyflow/react";
import { ServiceNode } from "./service-node";
import { Button, Card, MultiSelect, MultiSelectItem } from "@tremor/react";
import {
  ArrowUpRightIcon,
  ArrowDownTrayIcon,
  ArrowUpTrayIcon,
  PlusIcon,
  ArrowPathIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import {
  edgeLabelBgStyleNoHover,
  edgeMarkerEndNoHover,
  edgeLabelBgStyleHover,
  edgeMarkerEndHover,
} from "./styles";
import "./topology.css";
import Loading from "@/app/(keep)/loading";
import { Link } from "@/components/ui";
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
import { useIncidents } from "@/utils/hooks/useIncidents";
import { EdgeBase, Connection } from "@xyflow/system";
import { AddEditNodeSidePanel } from "./AddEditNodeSidePanel";
import { useApi } from "@/shared/lib/hooks/useApi";
import {
  EmptyStateCard,
  ErrorComponent,
  showErrorToast,
  showSuccessToast,
} from "@/shared/ui";
import { downloadFileFromString } from "@/shared/lib/downloadFileFromString";
import { TbTopologyRing } from "react-icons/tb";
import { ImportTopologyModal } from "./ImportTopologyModal";
import { useAlerts } from "@/entities/alerts/model";

const defaultFitViewOptions: FitViewOptions = {
  padding: 0.1,
  minZoom: 0.3,
};

type TopologyMapProps = {
  topologyServices?: TopologyService[];
  topologyApplications?: TopologyApplication[];
  selectedApplicationIds?: string[];
  providerIds?: string[];
  services?: string[];
  environment?: string;
  isVisible?: boolean;
  standalone?: boolean;
  onPullTopology?: (e: React.MouseEvent) => Promise<void>;
};

export function TopologyMap({
  topologyServices: initialTopologyServices,
  topologyApplications: initialTopologyApplications,
  selectedApplicationIds: initialSelectedApplicationIds,
  providerIds,
  services,
  environment,
  isVisible = true,
  standalone = false,
  onPullTopology,
}: TopologyMapProps) {
  const [initiallyFitted, setInitiallyFitted] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);

  // Track if we're in incident view mode (fixed application selection)
  const isIncidentView = Boolean(
    initialSelectedApplicationIds && initialSelectedApplicationIds.length > 0
  );

  const {
    topologyData,
    isLoading,
    error,
    mutate: mutateTopologyData,
  } = useTopology({
    providerIds,
    services,
    environment,
    initialData: initialTopologyServices,
  });
  const { applications, mutate: mutateApplications } = useTopologyApplications({
    initialData: initialTopologyApplications,
  });
  const router = useRouter();

  const {
    selectedObjectId,
    setSelectedObjectId,
    selectedApplicationIds,
    setSelectedApplicationIds,
  } = useTopologySearchContext();

  // if initialSelectedApplicationIds is provided, set it as selectedApplicationIds
  useEffect(() => {
    // Only update when there are valid initial IDs provided as props
    if (
      initialSelectedApplicationIds &&
      initialSelectedApplicationIds.length > 0
    ) {
      setSelectedApplicationIds(initialSelectedApplicationIds);
    }
    // We only want this effect to run once on initial render or when prop changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSelectedApplicationIds]);

  // Separate effect to check for application changes
  useEffect(() => {
    // This is only needed for debugging
    if (selectedApplicationIds.length > 0) {
      console.log("Active application filters:", selectedApplicationIds);
    }
  }, [selectedApplicationIds]);

  const [isSidePanelOpen, setIsSidePanelOpen] = useState<boolean>(false);

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

  // Refs for storing data - all declared at component level
  const reactFlowInstanceRef = useRef<ReactFlowInstance<TopologyNode, Edge>>();
  const edgeReconnectSuccessful = useRef(true);
  const previousNodesIds = useRef<Set<string>>(new Set());
  // Refs for storing the complete node data
  const allNodesRef = useRef<TopologyNode[]>([]);
  const allEdgesRef = useRef<Edge[]>([]);

  // Warning state
  const [limitWarning, setLimitWarning] = useState<{
    show: boolean;
    totalNodes?: number;
    displayedNodes?: number;
  }>({ show: false });

  // Statistics about the topology
  const [topologyStats, setTopologyStats] = useState<{
    totalNodes: number;
    displayedNodes: number;
    totalEdges: number;
    displayedEdges: number;
  }>({
    totalNodes: 0,
    displayedNodes: 0,
    totalEdges: 0,
    displayedEdges: 0,
  });

  // Optional: "Show All" handler
  const handleShowAll = useCallback(() => {
    if (allNodesRef.current.length > 0) {
      // This might cause performance issues, warn the user
      const confirmShowAll = window.confirm(
        `Showing all ${allNodesRef.current.length} nodes may cause performance issues. Continue?`
      );

      if (confirmShowAll) {
        // Apply layout to all nodes - this will be slow for large graphs
        const fullLayoutedElements = getLayoutedElements(
          allNodesRef.current,
          allEdgesRef.current,
          true // Bypass the limit
        );

        setNodes(fullLayoutedElements.nodes);
        setEdges(fullLayoutedElements.edges);
        setLimitWarning({ show: false });
      }
    }
  }, []);

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

  const handleImportTopology = () => {
    setIsImportModalOpen(true);
  };

  const api = useApi();

  const handleExportTopology = async () => {
    try {
      const response = await api.get("/topology/export", {
        headers: {
          Accept: "application/x-yaml",
        },
      });
      downloadFileFromString({
        data: response,
        filename: "topology-export.yaml",
        contentType: "application/x-yaml",
      });
    } catch (error) {
      showErrorToast(error, "Error exporting topology");
    }
  };

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

  const getServiceById = useCallback(
    (_id: string) => {
      return topologyData?.find((service) => {
        return service.id === _id;
      });
    },
    [topologyData]
  );

  const onConnect = useCallback(
    async (params: EdgeBase | Connection) => {
      const sourceService = getServiceById(params.source);
      const targetService = getServiceById(params.target);
      if (
        sourceService?.is_manual === true &&
        targetService?.is_manual === true
      ) {
        setEdges((eds) => addEdge(params, eds));
        try {
          const response = await api.post("/topology/dependency", {
            service_id: sourceService.id,
            depends_on_service_id: targetService.id,
          });
          mutateTopologyData();
        } catch (error) {
          const edgeIdToRevert = `xy-edge__${sourceService.id}right-${targetService.id}left`;
          setEdges((eds) => eds.filter((e) => e.id !== edgeIdToRevert));
          showErrorToast(
            error,
            `Error while adding connection from ${params.source} to ${params.target}: ${error}`
          );
        }
      }
    },
    [api, getServiceById, mutateTopologyData]
  );

  const onReconnectStart = useCallback(() => {
    edgeReconnectSuccessful.current = false;
  }, []);

  const onReconnect = useCallback(
    async (oldEdge: EdgeBase, newConnection: Connection) => {
      edgeReconnectSuccessful.current = true;
      if (
        getServiceById(oldEdge.source)?.is_manual === false ||
        getServiceById(oldEdge.target)?.is_manual === false ||
        getServiceById(newConnection.source)?.is_manual === false ||
        getServiceById(newConnection.target)?.is_manual === false
      ) {
        return;
      }
      if (
        oldEdge.source === newConnection.source &&
        oldEdge.target === newConnection.target
      ) {
        return;
      } else {
        setEdges((els) => reconnectEdge(oldEdge, newConnection, els));
        try {
          const response = await api.put("/topology/dependency", {
            id: oldEdge.id,
            service_id: newConnection.source,
            depends_on_service_id: newConnection.target,
          });
          mutateTopologyData();
        } catch (error) {
          setEdges((eds) => eds.filter((e) => e.id !== oldEdge.id));
          setEdges((eds) => addEdge(oldEdge, eds));
          showErrorToast(
            error,
            `Error while adding (re)connection from ${newConnection.source} to ${newConnection.target}`
          );
        }
      }
    },
    [api, mutateTopologyData, getServiceById]
  );

  const getEdgeIdBySourceTarget = useCallback(
    (source: string, target: string) => {
      const sourceNode = topologyData?.find((node) => node.id === source);
      const edge = sourceNode?.dependencies.find(
        (deps) => deps.serviceId === target
      );
      return edge?.id;
    },
    [topologyData]
  );

  const onReconnectEnd = useCallback(
    async (_: MouseEvent | TouchEvent, edge: Edge) => {
      if (
        getServiceById(edge.source)?.is_manual === false ||
        getServiceById(edge.target)?.is_manual === false
      ) {
        return;
      }

      if (!edgeReconnectSuccessful.current) {
        setEdges((eds) => eds.filter((e) => e.id !== edge.id));
        try {
          const edgeId = getEdgeIdBySourceTarget(edge.source, edge.target);
          const response = await api.delete(`/topology/dependency/${edgeId}`);
          mutateTopologyData();
          // setEdges((eds) => eds.filter((e) => e.id !== edge.id));
        } catch (error) {
          setEdges((eds) => addEdge(edge, eds));
          showErrorToast(
            error,
            `Failed to delete connection from ${edge.source} to ${edge.target}`
          );
        }
      }
      edgeReconnectSuccessful.current = true;
    },
    [mutateTopologyData, getEdgeIdBySourceTarget, api, getServiceById]
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

  const handleSelectFromSearch = useCallback(
    ({
      value,
    }: {
      value: TopologyServiceMinimal | TopologyApplicationMinimal;
    }) => {
      if ("service" in value) {
        setSelectedObjectId(value.id);
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

  const { data: allIncidents } = useIncidents({});
  const { useLastAlerts } = useAlerts();
  const { data: allAlerts } = useLastAlerts(undefined);

  // Fixed useEffect with properly organized refs
  useEffect(
    function createAndSetLayoutedNodesAndEdges() {
      if (!topologyData) {
        return;
      }

      const { nodeMap, edgeMap } = getNodesAndEdgesFromTopologyData(
        topologyData,
        applicationMap,
        allIncidents?.items ?? [],
        allAlerts ?? [],
        mutateTopologyData
      );

      const newNodes = Array.from(nodeMap.values());
      const newEdges = Array.from(edgeMap.values());

      // Store the complete set of nodes and edges in refs for potential use later
      allNodesRef.current = newNodes;
      allEdgesRef.current = newEdges;

      if (
        previousNodesIds.current.size > 0 &&
        areSetsEqual(previousNodesIds.current, new Set(nodeMap.keys()))
      ) {
        // No need to update positions here since getLayoutedElements will return a new set of nodes
        previousNodesIds.current = new Set(nodeMap.keys());
      } else {
        previousNodesIds.current = new Set(nodeMap.keys());
      }

      // If we have initial selected applications, immediately apply those filters
      // instead of showing the default limited view
      if (
        initialSelectedApplicationIds &&
        initialSelectedApplicationIds.length > 0
      ) {
        // The watchSelectedApplications effect will handle this after state updates
        return;
      }

      const layoutedElements = getLayoutedElements(newNodes, newEdges);

      // Set state for nodes and edges - now only using the limited set
      setNodes(layoutedElements.nodes);
      setEdges(layoutedElements.edges);

      // Store the total counts for potential use
      setTopologyStats({
        totalNodes: newNodes.length,
        displayedNodes: layoutedElements.nodes.length,
        totalEdges: newEdges.length,
        displayedEdges: layoutedElements.edges.length,
      });

      // Show warning banner if node limit was applied
      if (layoutedElements.metadata?.limitApplied) {
        setLimitWarning({
          show: true,
          totalNodes: layoutedElements.metadata.totalNodes,
          displayedNodes: layoutedElements.metadata.displayedNodes,
        });
      } else {
        setLimitWarning({ show: false });
      }
    },
    [
      topologyData,
      applicationMap,
      allIncidents,
      mutateTopologyData,
      initialSelectedApplicationIds,
    ]
  );

  useEffect(
    function watchSelectedApplications() {
      if (selectedApplicationIds.length === 0) {
        // When no applications are selected, we need to go back to the
        // limited view to avoid performance issues with large topologies

        // Re-apply the original layout with limits (don't bypass)
        const layoutedElements = getLayoutedElements(
          allNodesRef.current,
          allEdgesRef.current,
          false, // Don't bypass limit
          false // Not in application mode
        );

        // Update nodes and edges with the original limited layout
        setNodes(layoutedElements.nodes);
        setEdges(layoutedElements.edges);

        // Restore the original topology stats
        setTopologyStats({
          totalNodes: allNodesRef.current.length,
          displayedNodes: layoutedElements.nodes.length,
          totalEdges: allEdgesRef.current.length,
          displayedEdges: layoutedElements.edges.length,
        });

        // Show the warning banner if node limit was applied
        if (layoutedElements.metadata?.limitApplied) {
          setLimitWarning({
            show: true,
            totalNodes: layoutedElements.metadata.totalNodes,
            displayedNodes: layoutedElements.metadata.displayedNodes,
          });
        }

        // Fit view to the visible nodes
        setTimeout(() => {
          reactFlowInstanceRef.current?.fitView(defaultFitViewOptions);
        }, 0);

        return;
      }

      // Get all service nodes that are part of selected applications
      const selectedServiceNodesIds = new Set(
        applications.flatMap((app) =>
          selectedApplicationIds.includes(app.id)
            ? app.services.map((s) => s.id.toString())
            : []
        )
      );

      // When applications are selected, let's use only the nodes and edges
      // that are part of the selected applications, but bypass the limit
      const filteredNodes = allNodesRef.current.filter(
        (n) => n.type !== "service" || selectedServiceNodesIds.has(n.id)
      );

      const filteredEdges = allEdgesRef.current.filter(
        (e) =>
          selectedServiceNodesIds.has(e.source) &&
          selectedServiceNodesIds.has(e.target)
      );

      // Apply layout with application mode to handle larger sets with a higher limit
      const layoutedElements = getLayoutedElements(
        filteredNodes,
        filteredEdges,
        false, // Don't bypass the limit completely
        true // Use application mode with higher limits
      );

      // Update nodes and edges with the newly layouted elements
      setNodes(layoutedElements.nodes);
      setEdges(layoutedElements.edges);

      // Update stats to reflect what we're displaying
      setTopologyStats((prev) => ({
        ...prev,
        displayedNodes: layoutedElements.nodes.length,
        displayedEdges: layoutedElements.edges.length,
      }));

      // Show warning if we had to limit application nodes
      if (layoutedElements.metadata?.limitApplied) {
        setLimitWarning({
          show: true,
          totalNodes: layoutedElements.metadata.totalNodes,
          displayedNodes: layoutedElements.metadata.displayedNodes,
        });
      } else {
        // Hide the limit warning if there's no limit applied
        setLimitWarning({ show: false });
      }

      // Then fit view to the nodes
      setTimeout(() => {
        reactFlowInstanceRef.current?.fitView({
          padding: 0.2,
          minZoom: 0.5,
          nodes: layoutedElements.nodes,
          duration: 300,
        });
      }, 0);
    },
    [
      applications,
      selectedApplicationIds,
      getLayoutedElements,
      defaultFitViewOptions,
    ]
  );

  if (isLoading) {
    return <Loading />;
  }
  if (error) {
    return (
      <div className="mt-20 flex flex-col justify-center">
        <ErrorComponent
          error={error || new Error("Error Loading Topology Data")}
          description="We encountered some problem while trying to load your topology data, please contact us if this issue continues"
          reset={() => {
            mutateTopologyData();
          }}
        />
      </div>
    );
  }

  return (
    <>
      <div className="flex flex-col gap-4 h-full">
        {/* Banner placed outside the flex layout for the controls */}
        {limitWarning.show && (
          <div className="bg-amber-50 w-full py-2 px-4 mb-2 flex justify-between items-center border-y border-amber-200">
            <div className="flex items-center">
              <span className="font-medium text-amber-800 mr-2">
                Limited View
              </span>
              <span className="text-amber-700">
                For performance reasons, only {limitWarning.displayedNodes} out
                of {limitWarning.totalNodes} nodes are displayed.
              </span>
            </div>
            <div className="flex items-center gap-4">
              <Button
                size="xs"
                color="amber"
                variant="secondary"
                onClick={handleShowAll}
                className="whitespace-nowrap"
              >
                Show All (May Affect Performance)
              </Button>
              <button
                className="text-amber-400 hover:text-amber-500"
                onClick={() => setLimitWarning({ show: false })}
              >
                <XMarkIcon className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
          </div>
        )}
        <div className="flex justify-between gap-4 items-center">
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
              placeholder={
                isIncidentView
                  ? "Application filter locked"
                  : "Show application"
              }
              value={selectedApplicationIds}
              onValueChange={(newValues) => {
                // Prevent changes if we're in incident view
                if (isIncidentView) {
                  return;
                }
                setSelectedApplicationIds(newValues);
              }}
              disabled={!applications.length || isIncidentView}
            >
              {applications.map((app) => (
                <MultiSelectItem key={app.id} value={app.id}>
                  {app.name}
                </MultiSelectItem>
              ))}
            </MultiSelect>
          </div>
          <div className="flex gap-2">
            {onPullTopology && (
              <>
                <Button
                  onClick={() => setIsSidePanelOpen(true)}
                  color="orange"
                  variant="primary"
                  size="md"
                  icon={PlusIcon}
                >
                  Add Node
                </Button>
                <Button
                  onClick={handleImportTopology}
                  color="orange"
                  variant="secondary"
                  size="md"
                  icon={ArrowUpTrayIcon}
                >
                  Import
                </Button>
                <Button
                  onClick={handleExportTopology}
                  color="orange"
                  variant="secondary"
                  size="md"
                  icon={ArrowDownTrayIcon}
                >
                  Export
                </Button>
                <Button
                  onClick={onPullTopology}
                  color="orange"
                  variant="secondary"
                  size="md"
                  icon={ArrowPathIcon}
                >
                  Pull from providers
                </Button>
              </>
            )}
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
          <div className="absolute bottom-4 left-4 z-30 bg-white bg-opacity-80 rounded-md px-2 py-1 text-xs text-gray-600">
            Displaying {topologyStats.displayedNodes} of{" "}
            {topologyStats.totalNodes} nodes
          </div>
          <ReactFlowProvider>
            <ManageSelection
              topologyMutator={mutateTopologyData}
              getServiceById={getServiceById}
            />
            <ReactFlow
              nodes={nodes}
              edges={edges}
              minZoom={0.1}
              snapToGrid
              fitView
              fitViewOptions={defaultFitViewOptions}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onReconnect={onReconnect}
              onReconnectStart={onReconnectStart}
              onReconnectEnd={onReconnectEnd}
              onConnect={onConnect}
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
                      className="mb-20 max-w-3xl min-h-72"
                      icon={TbTopologyRing}
                      title="No Topology Yet"
                      description="Start by connecting providers that support topology, import topology data or create a new topology manually"
                    >
                      <div className="flex gap-2">
                        <Button
                          color="orange"
                          variant="secondary"
                          size="md"
                          onClick={handleImportTopology}
                        >
                          Import
                        </Button>
                        <Button
                          color="orange"
                          variant="primary"
                          size="md"
                          onClick={() =>
                            router.push("/providers?labels=topology")
                          }
                        >
                          Connect Providers
                        </Button>
                      </div>
                    </EmptyStateCard>
                  </div>
                </div>
              </>
            ))}
        </Card>
      </div>

      {/* Import Modal */}
      <ImportTopologyModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        onSuccess={() => {
          mutateApplications();
          mutateTopologyData();
        }}
      />

      {/* Add Node Side Panel */}
      <AddEditNodeSidePanel
        isOpen={isSidePanelOpen}
        topologyMutator={mutateTopologyData}
        handleClose={() => {
          setIsSidePanelOpen(false);
        }}
      />
    </>
  );
}
