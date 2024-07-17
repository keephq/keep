import React, { useEffect, useCallback } from 'react';
import {
  ReactFlow,
  Node,
  Edge,
  useNodesState,
  useEdgesState,
  addEdge,
  NodeProps,
  EdgeProps,
  Connection,
  MiniMap,
  Controls,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

const connectionLineStyle = { stroke: '#ccc', strokeWidth: 3 };
const snapGrid: [number, number] = [20, 20];
const defaultViewport = { x: 0, y: 0, zoom: 0.5 };

const getHealthColor = (): string => {
  return 'gray';
};

interface ServiceNode extends Node {
  data: {
    label: string;
  };
}

interface ServiceEdge extends Edge {
    animated?: boolean;
  }

const generateMockData = ():  { nodes: ServiceNode[]; edges: ServiceEdge[] } => {
  const nodes: ServiceNode[] = [];
  const edges: Edge[] = [];
  const services = [
    'Web App', 'DB', 'MongoDB', 'Snowflake', 'Cache', 'Auth Service', 'Payment Gateway',
    'Notification Service', 'Analytics Engine', 'Search Service', 'Third Party API 1', 'Third Party API 2'
  ];

  const layout = [1, 2, 3, 2, 4, 2];
  const rowHeight = 200;
  const columnWidth = 250;

  let currentIndex = 0;
  let yOffset = 0;

  layout.forEach((rowCount, rowIndex) => {
    const xOffset = (6 - rowCount) * columnWidth / 2;
    for (let i = 0; i < rowCount; i++) {
      if (currentIndex < services.length) {
        nodes.push({
          id: `${currentIndex + 1}`,
          type: 'default',
          data: { label: services[currentIndex] },
          position: { x: xOffset + i * columnWidth, y: yOffset },
          style: {
            background: getHealthColor(),
            color: '#fff',
            borderRadius: '50%',
            padding: 10,
            width: 120,
            height: 120,
            textAlign: 'center',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '14px'
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
      style: { stroke: '#ccc', strokeWidth: 3 },
    });
  }

  return { nodes, edges };
};

interface GraphVisualizationProps {
  demoMode: boolean;
}

const GraphVisualization: React.FC<GraphVisualizationProps> = ({ demoMode }) => {
    const [nodes, setNodes, onNodesChange] = useNodesState<ServiceNode>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<ServiceEdge>([]);

    useEffect(() => {
      const { nodes: mockNodes, edges: mockEdges } = generateMockData();
      setNodes(mockNodes);
      setEdges(mockEdges);
    }, []);

    const onConnect = useCallback(
        (params: Connection) =>
          setEdges((eds) =>
            addEdge({
              ...params,
              animated: true,
            }, eds).map(edge => ({
              ...edge,
              style: { stroke: '#ccc', strokeWidth: 3 }
            }))
          ),
        []
      );

  const onNodeClick = (event: React.MouseEvent, node: Node) => {
    window.open('https://github.com/keephq/keep/discussions/1377', '_blank');
  };

  return (
    <div style={{ height: 700, position: 'relative', background: '#f0f0f0' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        style={{ background: '#f0f0f0' }}
        connectionLineStyle={connectionLineStyle}
        snapToGrid={true}
        snapGrid={snapGrid}
        defaultViewport={defaultViewport}
        fitView
        attributionPosition="bottom-left"
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <MiniMap
          nodeStrokeColor={(n: Node) => n.style?.background as string}
          nodeColor={(n: Node) => n.style?.background as string}
        />
        <Controls />
      </ReactFlow>
      {demoMode && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(255, 255, 255, 0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          zIndex: 10,
          pointerEvents: 'none',
        }}>
          <h2 style={{ color: 'gray', marginBottom: '10px', fontSize: '32px' }}>Service Map</h2>
          <p style={{ color: 'gray', fontSize: '20px' }}>Connect your service map provider to use this feature.</p>
        </div>
      )}
    </div>
  );
};

export default GraphVisualization;
