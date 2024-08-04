import React from "react";
import { ReactFlow, Background, Controls, EdgeTypes as EdgeTypesType } from "@xyflow/react";
import CustomNode from "./CustomNode";
import CustomEdge from "./CustomEdge";
import useWorkflowInitialization from "utils/hooks/useWorkflowInitialization";
import "@xyflow/react/dist/style.css";
import DragAndDropSidebar from "./ToolBox";
import { Provider } from "app/providers/providers";
import ReactFlowEditor from "./ReactFlowEditor";

const nodeTypes = { custom: CustomNode };
const edgeTypes: EdgeTypesType = { "custom-edge": CustomEdge as React.ComponentType<any> };

const ReactFlowBuilder = ({
  workflow,
  loadedAlertFile,
  providers,
  toolboxConfiguration,
}: {
  workflow: string | undefined;
  loadedAlertFile: string | null;
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
    <div className="sqd-designer-react">
      <div className="sqd-designer sqd-theme-light sqd-layout-desktop">
        <DragAndDropSidebar toolboxConfiguration={toolboxConfiguration}/>
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
            <Controls orientation="horizontal"/>
            <Background/>
          </ReactFlow>
        )}
        <ReactFlowEditor />
      </div>
    </div>
  );
};

export default ReactFlowBuilder;
