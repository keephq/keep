export interface TopologyNode {
  id: string;
  name: string;
  type: "service" | "database" | "cache" | "queue" | "external";
  provider?: string; // If fetched from 3rd party
  metadata: {
    [key: string]: any;
  };
  isEditable: boolean;
}

export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  type: "sync" | "async" | "dependency";
  metadata: {
    [key: string]: any;
  };
}

export interface Topology {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}
