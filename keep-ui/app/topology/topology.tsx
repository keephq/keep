"use client";
import { Card } from "@tremor/react";
import { ReactFlow, Controls } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useState } from "react";
import CustomNode from "./custom-node";

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

interface ServiceDependency {
  calls: string[];
}

const serviceDependencies: { [serviceName: string]: ServiceDependency } = {
  api: { calls: ["cart", "orders"] },
  cart: { calls: ["db"] },
  orders: { calls: ["db"] },
  db: { calls: [] },
};

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

const serviceDefinitions: { [serviceId: string]: Service } = {
  api: api,
};

const getPosition = (index: number, level: number) => ({
  x: level * 200,
  y: index * 100,
});

const TopologyPage = () => {
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<
    { id: string; source: string; target: string }[]
  >([]);

  useEffect(() => {
    const levels: any = {};
    Object.keys(serviceDependencies).forEach((service, index) => {
      levels[service] = 0;
    });

    const newNodes = Object.keys(serviceDependencies).map((service, index) => ({
      id: service,
      data: {
        label: service,
        displayName: serviceDefinitions[service]?.display_name,
        description: serviceDefinitions[service]?.description,
        team: serviceDefinitions[service]?.team,
        email: serviceDefinitions[service]?.email,
      },
      position: getPosition(index, levels[service]),
    }));

    const newEdges: { id: string; source: string; target: string }[] = [];
    Object.keys(serviceDependencies).forEach((service, level) => {
      serviceDependencies[service].calls.forEach((dependency, index) => {
        levels[dependency] = level + 1;
        newEdges.push({
          id: `${service}-${dependency}`,
          source: service,
          target: dependency,
        });
      });
    });

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
