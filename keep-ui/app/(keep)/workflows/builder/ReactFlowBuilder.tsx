import React from "react";
import {
  ReactFlow,
  Background,
  Controls,
  EdgeTypes as EdgeTypesType,
  useReactFlow,
} from "@xyflow/react";
import CustomNode from "./CustomNode";
import CustomEdge from "./CustomEdge";
import { useWorkflowStore } from "./workflow-store";
import DragAndDropSidebar from "./ToolBox";
import { Provider } from "@/app/(keep)/providers/providers";
import ReactFlowEditor from "./ReactFlowEditor";
import "@xyflow/react/dist/style.css";

const nodeTypes = { custom: CustomNode as any };
const edgeTypes: EdgeTypesType = {
  "custom-edge": CustomEdge as React.ComponentType<any>,
};

const ReactFlowBuilder = ({
  providers,
  installedProviders,
}: {
  providers: Provider[] | undefined | null;
  installedProviders: Provider[] | undefined | null;
}) => {
  const {
    nodes,
    edges,
    onEdgesChange,
    onNodesChange,
    onConnect,
    onDragOver,
    onDrop,
    isLoading,
  } = useWorkflowStore();

  const { screenToFlowPosition } = useReactFlow();

  const handleDrop = React.useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      onDrop(event, () => screenToFlowPosition({ x: 0, y: 0 }));
    },
    [screenToFlowPosition, onDrop]
  );

  return (
    <div className="h-[inherit] rounded-lg">
      <div className="h-full sqd-theme-light sqd-layout-desktop">
        <DragAndDropSidebar isDraggable={false} />
        {!isLoading && (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onDrop={handleDrop}
            onDragOver={onDragOver}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
          >
            <Controls orientation="horizontal" />
            <Background />
          </ReactFlow>
        )}
        <ReactFlowEditor
          providers={providers}
          installedProviders={installedProviders}
        />
      </div>
    </div>
  );
};

export default ReactFlowBuilder;
