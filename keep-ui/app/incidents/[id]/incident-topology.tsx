// Todo: This is ChatGPT code, need to replace with our code
// This is just for mock!
// Todo: auto center viewport

import React, { useState } from "react";
import {
  ReactFlow,
  Node,
  Edge,
  Controls,
  ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const connectionLineStyle = { stroke: "#ccc", strokeWidth: 3 };

const getHealthColor = (): string => {
  return "gray";
};

interface ServiceNode extends Node {
  data: {
    label: string;
  };
}

interface ServiceEdge extends Edge {
  animated?: boolean;
}

const generateMockData = (): { nodes: ServiceNode[]; edges: ServiceEdge[] } => {
  const nodes: ServiceNode[] = [];
  const edges: Edge[] = [];
  const services = [
    "Web App",
    "DB",
    "MongoDB",
    "Snowflake",
    "Cache",
    "Auth Service",
    "Payment Gateway",
    "Notification Service",
    "Analytics Engine",
    "Search Service",
    "Third Party API 1",
    "Third Party API 2",
  ];

  const layout = [1, 2, 3, 2, 4, 2];
  const rowHeight = 200;
  const columnWidth = 250;

  let currentIndex = 0;
  let yOffset = 0;

  layout.forEach((rowCount, rowIndex) => {
    const xOffset = ((6 - rowCount) * columnWidth) / 2;
    for (let i = 0; i < rowCount; i++) {
      if (currentIndex < services.length) {
        nodes.push({
          id: `${currentIndex + 1}`,
          type: "default",
          data: { label: services[currentIndex] },
          position: { x: xOffset + i * columnWidth, y: yOffset },
          style: {
            background: getHealthColor(),
            color: "#fff",
            borderRadius: "50%",
            padding: 10,
            width: 120,
            height: 120,
            textAlign: "center",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "14px",
          },
        });
        currentIndex++;
      }
    }
    yOffset += rowHeight;
  });

  for (let i = 0; i < services.length - 1; i++) {
    edges.push({
      id: `e${i + 1}-${i + 2}`,
      source: `${i + 1}`,
      target: `${i + 2}`,
      animated: true,
      style: { stroke: "#ccc", strokeWidth: 3 },
    });
  }

  return { nodes, edges };
};

const IncidentTopology = () => {
  const { nodes, edges } = generateMockData();
  const [instance, setInstance] = useState<ReactFlowInstance<
    ServiceNode,
    ServiceEdge
  > | null>(null);
  return (
    <div className="w-full h-[700px] relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        connectionLineStyle={connectionLineStyle}
        fitView={true}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        onViewportChange={(viewPort) => console.log(viewPort)}
        onInit={(instance) => setInstance(instance)}
      >
        <Controls />
      </ReactFlow>

      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: "rgba(255, 255, 255, 0.8)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          zIndex: 10,
          pointerEvents: "none",
        }}
      >
        <h2 style={{ color: "gray", marginBottom: "10px", fontSize: "32px" }}>
          Coming soon...
        </h2>
      </div>
    </div>
  );
};

export default IncidentTopology;
