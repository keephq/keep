import { Topology, TopologyNode, TopologyEdge } from "../models/Topology";

export class TopologyService {
  private topology: Topology = {
    nodes: [],
    edges: [],
  };

  // Add new node
  async addNode(node: Omit<TopologyNode, "id">): Promise<TopologyNode> {
    const newNode: TopologyNode = {
      ...node,
      id: generateUniqueId(),
      isEditable: !node.provider, // Third party nodes are not editable
    };
    this.topology.nodes.push(newNode);
    return newNode;
  }

  // Add new edge
  async addEdge(edge: Omit<TopologyEdge, "id">): Promise<TopologyEdge> {
    const newEdge: TopologyEdge = {
      ...edge,
      id: generateUniqueId(),
    };
    this.topology.edges.push(newEdge);
    return newEdge;
  }

  // Update node if editable
  async updateNode(
    id: string,
    updates: Partial<TopologyNode>
  ): Promise<TopologyNode | null> {
    const node = this.topology.nodes.find((n) => n.id === id);
    if (!node || !node.isEditable) return null;

    Object.assign(node, updates);
    return node;
  }

  // Delete node and its connected edges
  async deleteNode(id: string): Promise<boolean> {
    const node = this.topology.nodes.find((n) => n.id === id);
    if (!node || !node.isEditable) return false;

    this.topology.nodes = this.topology.nodes.filter((n) => n.id !== id);
    this.topology.edges = this.topology.edges.filter(
      (e) => e.source !== id && e.target !== id
    );
    return true;
  }

  // Get full topology
  async getTopology(): Promise<Topology> {
    return this.topology;
  }
}

function generateUniqueId(): string {
  return Math.random().toString(36).substr(2, 9);
}
