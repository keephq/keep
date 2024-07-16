import { Card } from "@tremor/react";
import { ReactFlow, Controls } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

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

const TopologyPage = () => {
  const nodes = Object.keys(serviceDependencies).map((service, index) => ({
    id: service,
    data: { label: service },
    position: { x: Math.random() * 600, y: Math.random() * 400 },
  }));

  const edges: {
    id: string;
    source: string;
    target: string;
  }[] = [];
  Object.keys(serviceDependencies).forEach((service) => {
    serviceDependencies[service].calls.forEach((dependency) => {
      edges.push({
        id: `${service}-${dependency}`,
        source: service,
        target: dependency,
      });
    });
  });

  return (
    <Card className="p-4 md:p-10 mx-auto h-full">
      <ReactFlow nodes={nodes} edges={edges}>
        <Controls />
      </ReactFlow>
    </Card>
  );
};

export default TopologyPage;
