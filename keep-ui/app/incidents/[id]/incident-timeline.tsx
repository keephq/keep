import React, { useCallback, useEffect } from "react";
import {
  ReactFlow,
  Node,
  Edge,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import ELK from "elkjs/lib/elk.bundled.js";
import { useAlerts } from "utils/hooks/useAlerts";
import { IncidentDto } from "../model";
import { useIncidentAlerts } from "utils/hooks/useIncidents";
import { timeFormat } from "d3-time-format";

// Define the props interface for the IncidentFlow component
interface Props {
  incident: IncidentDto;
}

// Type definitions for Nodes and Edges
type AlertNode = Node<{ label: string }>;
type AlertEdge = Edge<{ animated?: boolean }>;

// Initialize ELK instance
const elk = new ELK();

// ELK layout options
const elkOptions = {
  "elk.algorithm": "layered",
  "elk.direction": "RIGHT",
  "elk.layered.spacing.edgeNodeBetweenLayers": "40",
  "elk.spacing.nodeNode": "40",
  "elk.layered.nodePlacement.strategy": "SIMPLE",
};

// Helper to format time for display
const formatTime = timeFormat("%b %d, %I:%M %p");

// Function to calculate and apply ELK layout
const getLayoutedElements = async (
  nodes: AlertNode[],
  edges: AlertEdge[],
  options: any = {}
) => {
  const isHorizontal = true;
  const graph = {
    id: "root",
    layoutOptions: options,
    children: nodes.map((node) => ({
      ...node,
      targetPosition: isHorizontal ? "left" : "top",
      sourcePosition: isHorizontal ? "right" : "bottom",
      width: 150,
      height: 50,
    })),
    edges: edges.map((edge) => ({
      ...edge,
    })),
  };

  const layoutedGraph = await elk.layout(graph as any);
  return {
    nodes: layoutedGraph.children?.map((node: any) => ({
      ...node,
      position: { x: node.x, y: node.y },
    })),
    edges: layoutedGraph.edges,
  };
};

// Generate nodes and edges from alert events
const generateNodesAndEdges = (
  alerts: any[],
  auditEvents: any[],
  incidentStart: Date
): { nodes: AlertNode[]; edges: AlertEdge[] } => {
  const nodes: AlertNode[] = [];
  const edges: AlertEdge[] = [];

  // Incident start node
  nodes.push({
    id: "incident-start",
    data: { label: `Incident Start (${formatTime(incidentStart)})` },
    position: { x: 50, y: 50 },
    type: "input",
  });

  // Create nodes and edges for each fingerprint and its related events
  alerts.forEach((alert, alertIndex) => {
    const alertEvents = auditEvents
      .filter((event) => event.fingerprint === alert.fingerprint)
      .sort(
        (a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );

    alertEvents.forEach((event, eventIndex) => {
      const alertNodeId = `alert-${alertIndex}-${eventIndex}`;
      const timestamp = new Date(event.timestamp);

      // Create a node for each alert event
      nodes.push({
        id: alertNodeId,
        data: { label: `${event.action} (${formatTime(timestamp)})` },
        position: { x: 0, y: 0 },
        style: {
          background: getAlertStatusColor(event.status),
          color: "white",
        },
      });

      // Connect the incident start to the first event, and subsequent events for each fingerprint
      if (eventIndex === 0) {
        edges.push({
          id: `edge-${alertIndex}-start`,
          source: "incident-start",
          target: alertNodeId,
          animated: false,
        });
      } else {
        edges.push({
          id: `edge-${alertIndex}-${eventIndex}`,
          source: `alert-${alertIndex}-${eventIndex - 1}`,
          target: alertNodeId,
          animated: false,
        });
      }
    });
  });

  return { nodes, edges };
};

// Helper function to get status color based on alert status
const getAlertStatusColor = (status: string): string => {
  const colors: Record<string, string> = {
    critical: "red",
    warning: "orange",
    resolved: "green",
    acknowledged: "blue",
    suppressed: "gray",
  };
  return colors[status] || "gray";
};

const IncidentFlow: React.FC<Props> = ({ incident }) => {
  const { data: alerts, isLoading: alertsLoading } = useIncidentAlerts(
    incident.id
  );
  const { useMultipleFingerprintsAlertAudit } = useAlerts();
  const { data: auditEvents, isLoading } = useMultipleFingerprintsAlertAudit(
    alerts?.items.map((m) => m.fingerprint)
  );

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (!alertsLoading && !isLoading && auditEvents && alerts) {
      // Get the incident start time (earliest event timestamp)
      const incidentStart = new Date(
        Math.min(
          ...auditEvents.map((e: any) => new Date(e.timestamp).getTime())
        )
      );

      // Generate nodes and edges from alert data
      const { nodes: initialNodes, edges: initialEdges } =
        generateNodesAndEdges(
          alerts.items || [],
          auditEvents || [],
          incidentStart
        );

      // Apply ELK layout to the generated nodes and edges
      getLayoutedElements(initialNodes, initialEdges, elkOptions).then(
        ({ nodes: layoutedNodes, edges: layoutedEdges }) => {
          setNodes(layoutedNodes as any);
          setEdges(layoutedEdges as any);
        }
      );
    }
  }, [alerts, auditEvents, alertsLoading, isLoading]);

  if (isLoading || alertsLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div style={{ height: "500px", width: "100%" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        nodesDraggable={false}
      >
        <Background variant={BackgroundVariant.Cross} gap={12} size={1} />
        <Controls />
      </ReactFlow>
    </div>
  );
};

export default IncidentFlow;
