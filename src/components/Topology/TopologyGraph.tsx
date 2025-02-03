import React, { useEffect, useState } from "react";
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  ConnectionMode,
} from "reactflow";
import "reactflow/dist/style.css";
import { TopologyService } from "../../services/TopologyService";
import { TopologyNode, TopologyEdge } from "../../models/Topology";

interface TopologyGraphProps {
  topologyService: TopologyService;
}

export const TopologyGraph: React.FC<TopologyGraphProps> = ({
  topologyService,
}) => {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  useEffect(() => {
    loadTopology();
  }, []);

  const loadTopology = async () => {
    const topology = await topologyService.getTopology();

    // Convert topology nodes to ReactFlow nodes
    const flowNodes = topology.nodes.map((node) => ({
      id: node.id,
      type: "custom",
      data: { ...node },
      position: node.metadata.position || { x: 0, y: 0 },
      draggable: node.isEditable,
    }));

    // Convert topology edges to ReactFlow edges
    const flowEdges = topology.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: edge.type,
      data: edge.metadata,
    }));

    setNodes(flowNodes);
    setEdges(flowEdges);
  };

  const onConnect = async (params: any) => {
    const newEdge = await topologyService.addEdge({
      source: params.source,
      target: params.target,
      type: "sync",
      metadata: {},
    });
    setEdges((prev) => [...prev, newEdge]);
  };

  return (
    <div style={{ width: "100%", height: "100vh" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onConnect={onConnect}
        connectionMode={ConnectionMode.Strict}
        fitView
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
};
