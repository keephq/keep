import React, { useEffect, useState, useCallback } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  useNodesState,
  useEdgesState,
  ReactFlowProvider,
  Panel,
  Node,
  Edge,
  NodeChange,
  EdgeChange,
  ReactFlowInstance,
  OnInit,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Text } from "@tremor/react";
import dagre from "@dagrejs/dagre";

// Define types for services and dependencies
interface TopologyService {
  id?: string;
  service?: string;
  display_name?: string;
  environment?: string;
}

interface TopologyDependency {
  service_id?: string;
  depends_on_service_id?: string;
  source?: string;
  target?: string;
  protocol?: string;
}

interface Component {
  nodeIds: Set<string>;
  nodes: Node[];
  edges: Edge[];
}

// Node styling with better visual hierarchy
const serviceNodeStyle: React.CSSProperties = {
  padding: 10,
  borderRadius: 5,
  border: "1px solid #ddd",
  background: "#f5f5f5",
  color: "#333",
  textAlign: "center",
  width: 150,
  fontSize: "11px",
  boxShadow: "0 1px 2px rgba(0,0,0,0.1)",
};

// Advanced layout function with better space utilization
const getLayoutedElements = (
  nodes: Node[],
  edges: Edge[],
  direction = "LR",
  nodeWidth = 150,
  nodeHeight = 50
): { nodes: Node[]; edges: Edge[] } => {
  if (!nodes || nodes.length === 0) return { nodes: [], edges: [] };

  // Create a copy of the nodes and edges to avoid modifying the originals
  const nodesCopy = [...nodes];
  const edgesCopy = [...edges];

  // Phase 1: Use dagre for initial layout (helps establish hierarchy)
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  // Use larger spacing parameters to spread things out horizontally
  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 120, // Increased horizontal spacing between nodes on same rank
    ranksep: 100, // Increased vertical spacing between ranks
    marginx: 50,
    marginy: 50,
    acyclicer: "greedy", // Help with any cycles in the graph
    ranker: "network-simplex", // Better for complex graphs
  });

  // Add nodes to dagre
  nodesCopy.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  // Add edges to dagre
  edgesCopy.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  // Calculate layout
  dagre.layout(dagreGraph);

  // Get layout bounds to help with node distribution
  let minX = Infinity,
    maxX = -Infinity,
    minY = Infinity,
    maxY = -Infinity;
  nodesCopy.forEach((node) => {
    const dagreNode = dagreGraph.node(node.id);
    if (dagreNode) {
      minX = Math.min(minX, dagreNode.x);
      maxX = Math.max(maxX, dagreNode.x);
      minY = Math.min(minY, dagreNode.y);
      maxY = Math.max(maxY, dagreNode.y);
    }
  });

  // Phase 2: Apply layout with some additional spacing adjustments
  // to better use the horizontal space
  const layoutedNodes = nodesCopy.map((node) => {
    const dagreNode = dagreGraph.node(node.id);

    if (dagreNode) {
      // Calculate how far along the x-axis this node is (0-1)
      const xProgress = (dagreNode.x - minX) / (maxX - minX || 1);

      // Apply a slight horizontal spreading factor to use more width
      // This pushes nodes that are at the extremes further out
      const spreadFactor = 1.3;
      const adjustedX = minX + (maxX - minX) * xProgress * spreadFactor;

      return {
        ...node,
        position: {
          x: adjustedX - nodeWidth / 2,
          y: dagreNode.y - nodeHeight / 2,
        },
      };
    }
    return node;
  });

  return { nodes: layoutedNodes, edges: edgesCopy };
};

// Filter edges to only include those between displayed nodes
const filterEdges = (
  edges: Edge[] | undefined,
  visibleNodeIds: string[]
): Edge[] => {
  if (!edges) return [];

  const visibleNodeIdSet = new Set(visibleNodeIds);
  return edges.filter(
    (edge) =>
      visibleNodeIdSet.has(edge.source) && visibleNodeIdSet.has(edge.target)
  );
};

// Function to find disconnected components in the graph
const findDisconnectedComponents = (
  nodes: Node[],
  edges: Edge[]
): Component[] => {
  // Create an adjacency map
  const adjacencyMap: Record<string, string[]> = {};
  nodes.forEach((node) => {
    adjacencyMap[node.id] = [];
  });

  edges.forEach((edge) => {
    if (adjacencyMap[edge.source]) {
      adjacencyMap[edge.source].push(edge.target);
    }
    if (adjacencyMap[edge.target]) {
      adjacencyMap[edge.target].push(edge.source);
    }
  });

  // Track visited nodes
  const visited = new Set<string>();
  const components: Component[] = [];

  // DFS to find connected components
  const dfs = (nodeId: string, component: Component): void => {
    visited.add(nodeId);
    component.nodeIds.add(nodeId);

    (adjacencyMap[nodeId] || []).forEach((neighbor) => {
      if (!visited.has(neighbor)) {
        dfs(neighbor, component);
      }
    });
  };

  // Find all components
  nodes.forEach((node) => {
    if (!visited.has(node.id)) {
      const component: Component = { nodeIds: new Set(), nodes: [], edges: [] };
      dfs(node.id, component);

      // Fill in the nodes and edges for this component
      component.nodes = nodes.filter((n) => component.nodeIds.has(n.id));
      component.edges = edges.filter(
        (e) =>
          component.nodeIds.has(e.source) && component.nodeIds.has(e.target)
      );

      components.push(component);
    }
  });

  return components;
};

// Limit nodes to the most important ones based on connections
const limitNodesByConnections = (
  nodes: Node[],
  edges: Edge[],
  maxNodes: number
): Node[] => {
  if (nodes.length <= maxNodes) return nodes;

  // Count connections for each node
  const connectionCounts: Record<string, number> = {};
  edges.forEach((edge) => {
    connectionCounts[edge.source] = (connectionCounts[edge.source] || 0) + 1;
    connectionCounts[edge.target] = (connectionCounts[edge.target] || 0) + 1;
  });

  // Sort nodes by connection count (most connected first)
  const sortedNodes = [...nodes].sort((a, b) => {
    const aCount = connectionCounts[a.id] || 0;
    const bCount = connectionCounts[b.id] || 0;
    return bCount - aCount;
  });

  // Take only the top maxNodes
  return sortedNodes.slice(0, maxNodes);
};

interface TopologyPreviewProps {
  services?: TopologyService[];
  dependencies?: TopologyDependency[];
  className?: string;
  height?: string;
  maxNodes?: number;
  direction?: string;
  rankSeparation?: number;
  nodeSeparation?: number;
}

const TopologyPreviewInner: React.FC<TopologyPreviewProps> = ({
  services,
  dependencies,
  className = "",
  height = "500px", // Increased default height for better visibility
  maxNodes = 200,
  direction = "LR", // Default to left-to-right for better visualization of dependencies
  rankSeparation = 100, // Controls vertical spacing
  nodeSeparation = 120, // Controls horizontal spacing
}) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [isLimited, setIsLimited] = useState<boolean>(false);
  const [totalNodes, setTotalNodes] = useState<number>(0);
  const [totalEdges, setTotalEdges] = useState<number>(0);
  const [nodesRendered, setNodesRendered] = useState<number>(0);
  const [edgesRendered, setEdgesRendered] = useState<number>(0);

  // Function to fit view after nodes are loaded
  const onInit: OnInit = useCallback((reactFlowInstance: ReactFlowInstance) => {
    reactFlowInstance.fitView({ padding: 0.2 });
  }, []);

  // Process nodes and edges when data changes
  useEffect(() => {
    if (!services || !dependencies) return;

    // Using proper state setters instead of console.log for debugging
    setTotalNodes(services.length);
    setTotalEdges(dependencies.length);
    setIsLimited(services.length > maxNodes);

    // Create nodes with unique IDs and compact labels
    const flowNodes: Node[] = services.map((service, index) => {
      const displayName = service.display_name || service.service || "";
      // Truncate long names for better layout
      const truncatedName =
        displayName.length > 25
          ? displayName.substring(0, 22) + "..."
          : displayName;

      return {
        id: (service.id || `svc-${index}`).toString(),
        data: {
          label: `${truncatedName}${
            service.environment ? `\n${service.environment}` : ""
          }`,
          fullName: displayName, // Store full name for tooltips if needed
        },
        position: { x: 0, y: 0 }, // Initial position - will be arranged by layout
        style: serviceNodeStyle,
      };
    });

    // Create edges with valid source/target IDs
    const flowEdges: Edge[] = dependencies.map((dep, index) => {
      const sourceId = (dep.service_id || dep.source || "").toString();
      const targetId = (
        dep.depends_on_service_id ||
        dep.target ||
        ""
      ).toString();

      return {
        id: `e-${index}`,
        source: sourceId,
        target: targetId,
        type: "smoothstep", // Improved edge type for better visualization
        animated: false,
        style: { stroke: "#888", strokeWidth: 1.5 },
        label: dep.protocol || "",
        labelStyle: { fill: "#666", fontSize: 9 },
        labelBgStyle: { fill: "rgba(255, 255, 255, 0.7)" },
      };
    });

    // Apply node limiting if needed - prioritize connected nodes
    let limitedNodes: Node[] = flowNodes;
    if (services.length > maxNodes) {
      limitedNodes = limitNodesByConnections(flowNodes, flowEdges, maxNodes);
    }

    const visibleNodeIds = limitedNodes.map((node) => node.id);
    const validEdges = filterEdges(flowEdges, visibleNodeIds);

    // Sometimes with large graphs, separation into disconnected subgraphs works better
    // Identify disconnected components and lay them out separately
    const components = findDisconnectedComponents(limitedNodes, validEdges);
    let finalNodes: Node[] = [];
    let horizontalOffset = 0;

    if (components.length > 1 && components.length <= 5) {
      // We have multiple components, lay them out side by side
      components.forEach((component) => {
        const { nodes: layoutedComponentNodes } = getLayoutedElements(
          component.nodes,
          component.edges,
          direction,
          130, // slightly smaller nodes for multiple components
          50
        );

        // Offset this component horizontally
        const offsetNodes = layoutedComponentNodes.map((node) => ({
          ...node,
          position: {
            x: node.position.x + horizontalOffset,
            y: node.position.y,
          },
        }));

        finalNodes = [...finalNodes, ...offsetNodes];

        // Calculate width of this component for next offset
        const componentWidth =
          Math.max(...layoutedComponentNodes.map((n) => n.position.x)) + 200;
        horizontalOffset += componentWidth;
      });
    } else {
      // Single layout for connected graph or too many components
      const { nodes: layoutedNodes } = getLayoutedElements(
        limitedNodes,
        validEdges,
        direction,
        140, // nodeWidth
        55 // nodeHeight
      );

      finalNodes = layoutedNodes;
    }

    setNodes(finalNodes);
    setEdges(validEdges);
    setNodesRendered(finalNodes.length);
    setEdgesRendered(validEdges.length);
  }, [services, dependencies, maxNodes, direction, setNodes, setEdges]);

  if (!services || !dependencies || services.length === 0) {
    return (
      <div
        className={`flex items-center justify-center border border-gray-200 rounded ${className}`}
        style={{ height }}
      >
        <Text>No preview data available</Text>
      </div>
    );
  }

  return (
    <div
      className={`border border-gray-200 rounded ${className}`}
      style={{ height, width: "100%" }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onInit={onInit}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={2}
        defaultViewport={{ x: 0, y: 0, zoom: 0.5 }}
        attributionPosition="bottom-right"
        nodesDraggable={false}
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
              Preview limited to {maxNodes} most connected nodes
            </div>
          )}
        </Panel>
      </ReactFlow>
    </div>
  );
};

// Wrap with Provider to ensure it works standalone
export const TopologyPreview: React.FC<TopologyPreviewProps> = (props) => (
  <ReactFlowProvider>
    <TopologyPreviewInner {...props} />
  </ReactFlowProvider>
);
