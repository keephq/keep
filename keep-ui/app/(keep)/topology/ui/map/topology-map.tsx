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
  EllipsisHorizontalIcon,
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
  DropdownMenu,
  EmptyStateCard,
  ErrorComponent,
  showErrorToast,
  showSuccessToast,
} from "@/shared/ui";
import { downloadFileFromString } from "@/shared/lib/downloadFileFromString";
import { PlusIcon } from "@heroicons/react/20/solid";
import { TbTopologyRing } from "react-icons/tb";

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
};

interface MenuItem {
  icon: ElementType;
  label: string;
  onClick: () => void;
}

export function TopologyMap({
  topologyServices: initialTopologyServices,
  topologyApplications: initialTopologyApplications,
  selectedApplicationIds: initialSelectedApplicationIds,
  providerIds,
  services,
  environment,
  isVisible = true,
  standalone = false,
}: TopologyMapProps) {
  const [initiallyFitted, setInitiallyFitted] = useState(false);

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
    if (initialSelectedApplicationIds) {
      setSelectedApplicationIds(initialSelectedApplicationIds);
    }
  }, [initialSelectedApplicationIds, setSelectedApplicationIds]);

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

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    if (!event.target.files) {
      return;
    }
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.set("file", file);

    try {
      const response = await api.request("/topology/import", {
        method: "POST",
        body: formData,
      });
      showSuccessToast("Topology imported Successfully!");
      mutateApplications();
      mutateTopologyData();
    } catch (error) {
      showErrorToast(error, "Error uploading file");
    }
  };

  const handleImportTopology = () => {
    const confirm = window.confirm(
      "Current topology will be completely replaced. Do you want to continue?"
    );
    if (confirm) {
      document.getElementById("fileInput")?.click();
    }
  };

  const menuItems: MenuItem[] = [
    {
      label: "Import",
      icon: ArrowUpTrayIcon,
      onClick: handleImportTopology,
    },
    {
      label: "Export",
      icon: ArrowDownTrayIcon,
      onClick: async () => {
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
      },
    },
  ];

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

  const api = useApi();
  const edgeReconnectSuccessful = useRef(true);

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

  const previousNodesIds = useRef<Set<string>>(new Set());

  const { data: allIncidents } = useIncidents();

  useEffect(
    function createAndSetLayoutedNodesAndEdges() {
      if (!topologyData) {
        return;
      }

      const { nodeMap, edgeMap } = getNodesAndEdgesFromTopologyData(
        topologyData,
        applicationMap,
        allIncidents?.items ?? [],
        mutateTopologyData
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
    [topologyData, applicationMap, allIncidents, mutateTopologyData]
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
            ? app.services.map((s) => s.id.toString())
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
          <div className="flex gap-2">
            <Button
              onClick={() => setIsSidePanelOpen(true)}
              color="orange"
              variant="primary"
              size="md"
              icon={PlusIcon}
            >
              Add Node
            </Button>
            <DropdownMenu.Menu icon={EllipsisHorizontalIcon} label="">
              {menuItems.map((item, index) => (
                <DropdownMenu.Item
                  key={item.label + index}
                  icon={item.icon}
                  label={item.label}
                  onClick={item.onClick}
                />
              ))}
            </DropdownMenu.Menu>
          </div>

          <input
            type="file"
            id="fileInput"
            className="hidden"
            onChange={handleFileUpload}
            accept=".yaml,.json,.csv"
          />

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
