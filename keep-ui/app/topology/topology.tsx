"use client";
import { Card } from "@tremor/react";
import { ReactFlow, Controls } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useState } from "react";
import CustomNode from "./custom-node";

// Service interface to define the structure of a service object
interface Service {
  id: string;
  last_modified_time?: Date;
  soruce_provider_id?: string;
  source_control_url?: string;
  tags?: string[];
  display_name: string;
  description?: string;
  team?: string;
  application?: string;
  code?: string;
  email?: string;
  slack?: string;
}

// ServiceDependency interface to define the structure of service dependencies
interface ServiceDependency {
  calls: string[];
}

// Mock data for service dependencies
const serviceDependencies: { [serviceName: string]: ServiceDependency } = {
  api: { calls: ["orders"] },
  cart: { calls: ["db"] },
  orders: { calls: ["db", "cart"] },
  db: { calls: [] },
};

// Mock data for service definitions
const api: Service = {
  id: "a77dd4bb-3701-411e-a352-93463e94fed3",
  last_modified_time: new Date(),
  soruce_provider_id: "api",
  source_control_url: "",
  tags: [],
  display_name: "API Service",
  description: "Handles all API requests",
  team: "DevOps",
  application: "Keep",
  email: "devops@keephq.dev",
  code: "python",
  slack: "devops-keep",
};

// Consolidated mock data for service definitions
const serviceDefinitions: { [serviceId: string]: Service } = {
  api: {
    id: "a77dd4bb-3701-411e-a352-93463e94fed3",
    last_modified_time: new Date(),
    soruce_provider_id: "api",
    source_control_url: "",
    tags: [],
    display_name: "API Service",
    description: "Handles all API requests",
    team: "DevOps",
    application: "Keep",
    email: "devops@keephq.dev",
    code: "python",
    slack: "devops-keep",
  },
  cart: {
    id: "cart",
    display_name: "Cart Service",
    description: "Handles cart operations",
    team: "E-commerce",
    email: "cart@keephq.dev",
  },
  orders: {
    id: "orders",
    display_name: "Orders Service",
    description: "Handles order processing",
    team: "E-commerce",
    email: "orders@keephq.dev",
  },
  db: {
    id: "db",
    display_name: "Database",
    description: "Handles data storage",
    team: "DevOps",
    email: "db@keephq.dev",
  },
};

// Helper function to determine the position of a node based on its index and level
const getPosition = (index: number, level: number) => ({
  x: level * 200,
  y: index * 100,
});

const TopologyPage = () => {
  // State for nodes and edges
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<
    { id: string; source: string; target: string }[]
  >([]);

  useEffect(() => {
    // Initialize levels for each service
    const levels: any = {};
    Object.keys(serviceDependencies).forEach((service) => {
      levels[service] = 0;
    });

    // Determine the level for each service based on its dependencies
    Object.keys(serviceDependencies).forEach((service) => {
      serviceDependencies[service].calls.forEach((dependency) => {
        levels[dependency] = Math.max(
          levels[dependency] || 0,
          levels[service] + 1
        );
      });
    });

    // Create nodes with positions based on their levels and index
    const newNodes = Object.keys(serviceDependencies).map((service, index) => ({
      id: service,
      type: "customNode",
      data: {
        label: service,
        displayName: serviceDefinitions[service]?.display_name,
        description: serviceDefinitions[service]?.description,
        team: serviceDefinitions[service]?.team,
        email: serviceDefinitions[service]?.email,
      },
      position: getPosition(index, levels[service]),
    }));

    // Create edges representing the calls between services
    const newEdges: any = [];
    Object.keys(serviceDependencies).forEach((service) => {
      serviceDependencies[service].calls.forEach((dependency) => {
        newEdges.push({
          id: `${service}-${dependency}`,
          source: service,
          target: dependency,
          markerEnd: {
            type: "arrowclosed",
          },
        });
      });
    });

    // Update state with the new nodes and edges
    setNodes(newNodes);
    setEdges(newEdges);
  }, []);

  return (
    <Card className="p-4 md:p-10 mx-auto h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodeTypes={{ customNode: CustomNode }}
      >
        <Controls />
      </ReactFlow>
    </Card>
  );
};

export default TopologyPage;
