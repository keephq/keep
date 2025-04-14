import React, { useEffect, useState } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  useNodesState,
  useEdgesState,
  ReactFlowProvider,
  Panel,
  FitViewOptions,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Text } from "@tremor/react";

// Refined node styling - optimized for better performance
const serviceNodeStyle = {
  padding: 5,
  borderRadius: 5,
  border: "1px solid #ddd",
  background: "#f5f5f5",
  color: "#333",
  textAlign: "center",
  width: 120,
  fontSize: "10px",
};

// Improved layout function with node limiting and pagination
const layoutNodes = (nodes, edges, maxNodes = 200) => {
  // If no nodes, return empty array
  if (!nodes || nodes.length === 0) return [];

  // Limit the number of nodes for display
  const limitedNodes =
    nodes.length > maxNodes ? nodes.slice(0, maxNodes) : nodes;

  // Set initial positions in a grid layout for better starting point
  const GRID_SIZE = Math.ceil(Math.sqrt(limitedNodes.length));
  const SPACING = 150;

  const positionedNodes = limitedNodes.map((node, i) => {
    const col = i % GRID_SIZE;
    const row = Math.floor(i / GRID_SIZE);

    return {
      ...node,
      position: {
        x: col * SPACING,
        y: row * SPACING,
      },
    };
  });

  return positionedNodes;
};

// Filter edges to only include those between displayed nodes
const filterEdges = (edges, visibleNodeIds) => {
  const visibleNodeIdSet = new Set(visibleNodeIds);
  return edges.filter(
    (edge) =>
      visibleNodeIdSet.has(edge.source) && visibleNodeIdSet.has(edge.target)
  );
};

const TopologyPreviewInner = ({
  services,
  dependencies,
  className = "h-64",
  height = "100%",
  maxNodes = 200, // Default limit of 200 nodes for preview
}) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [isLimited, setIsLimited] = useState(false);
  const [totalNodes, setTotalNodes] = useState(0);
  const [totalEdges, setTotalEdges] = useState(0);
  const [nodesRendered, setNodesRendered] = useState(0);
  const [edgesRendered, setEdgesRendered] = useState(0);

  const defaultFitViewOptions = {
    padding: 0.2,
    minZoom: 0.1,
    maxZoom: 1.5,
  };

  // Memory-optimized conversion of services and dependencies to ReactFlow nodes and edges
  useEffect(() => {
    if (!services || !dependencies) return;

    setTotalNodes(services.length);
    setTotalEdges(dependencies.length);
    setIsLimited(services.length > maxNodes);

    // Create a more efficient node representation - avoid complex nested objects
    const flowNodes = services.map((service, index) => ({
      id: service.id?.toString() || `svc-${index}`,
      data: {
        label: `${service.display_name || service.service}${
          service.environment ? `\n${service.environment}` : ""
        }`,
      },
      position: { x: 0, y: index * 50 }, // Initial positions - will be arranged by layout
      style: serviceNodeStyle,
    }));

    // Get the visible node IDs after limiting
    const visibleNodes = layoutNodes(flowNodes, [], maxNodes);
    const visibleNodeIds = visibleNodes.map((node) => node.id);

    // Filter dependencies to only include connections between visible nodes
    const visibleEdges = filterEdges(
      dependencies.map((dep, index) => ({
        id: `e-${index}`,
        source: (dep.service_id || dep.source)?.toString(),
        target: (dep.depends_on_service_id || dep.target)?.toString(),
        type: "default",
        animated: false,
        style: { stroke: "#888" },
        label: dep.protocol || "",
        labelStyle: { fill: "#888", fontSize: 8 },
        labelBgStyle: { fill: "rgba(255, 255, 255, 0.7)" },
      })),
      visibleNodeIds
    );

    // Update state with memory-efficient data
    setNodes(visibleNodes);
    setEdges(visibleEdges);
    setNodesRendered(visibleNodes.length);
    setEdgesRendered(visibleEdges.length);
  }, [services, dependencies, maxNodes, setNodes, setEdges]);

  if (!services || !dependencies || services.length === 0) {
    return (
      <div
        className={`flex items-center justify-center ${className}`}
        style={{ height }}
      >
        <Text>No preview data available</Text>
      </div>
    );
  }

  return (
    <div className={className} style={{ height }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        fitViewOptions={defaultFitViewOptions}
        minZoom={0.1}
        maxZoom={2}
        defaultViewport={{ x: 0, y: 0, zoom: 0.5 }}
        attributionPosition="bottom-right"
        style={{ background: "#ffffff" }}
        nodesDraggable={false} // Disable node dragging for better performance
      >
        <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
        <Controls />
        <Panel
          position="top-left"
          className="bg-white p-2 rounded shadow-sm text-xs"
        >
          <div>
            Services: {totalNodes} {isLimited && `(showing ${nodesRendered})`}
          </div>
          <div>
            Dependencies: {totalEdges}{" "}
            {isLimited && `(showing ${edgesRendered})`}
          </div>
          {isLimited && (
            <div className="text-amber-600 font-medium mt-1">
              Preview limited to {maxNodes} nodes for performance
            </div>
          )}
        </Panel>
      </ReactFlow>
    </div>
  );
};

// Wrap with Provider to ensure it works standalone
export const TopologyPreview = (props) => (
  <ReactFlowProvider>
    <TopologyPreviewInner {...props} />
  </ReactFlowProvider>
);
