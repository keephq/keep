import React from "react";
import { ReactFlow, Background, Controls } from "@xyflow/react";
import CustomNode from "./CustomNode";
import CustomEdge from "./CustomEdge";
import useWorkflowInitialization from "utils/hooks/useWorkflowInitialization";
import "@xyflow/react/dist/style.css";
import DragAndDropSidebar from "./ToolBox";
import { Provider } from "app/providers/providers";

const nodeTypes = { custom: CustomNode };
const edgeTypes = { "custom-edge": CustomEdge };

const ReactFlowBuilder = ({
  workflow,
  loadedAlertFile,
  providers,
  toolboxConfiguration,
}: {
  workflow: string;
  loadedAlertFile: string;
  providers: Provider[];
  toolboxConfiguration?: Record<string, any>;
}) => {
  const {
    nodes,
    edges,
    isLoading,
    onEdgesChange,
    onNodesChange,
    onConnect,
    onDragOver,
    onDrop,
  } = useWorkflowInitialization(workflow, loadedAlertFile, providers);


  return (
    <div className="flex flex-col space-between gap-2 w-full h-full">
      {!isLoading && (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onDrop={onDrop}
          onDragOver={onDragOver}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
        >
          <Controls />
          <Background />
        </ReactFlow>
      )}
      <DragAndDropSidebar />
    </div>
  );
};

export default ReactFlowBuilder;
