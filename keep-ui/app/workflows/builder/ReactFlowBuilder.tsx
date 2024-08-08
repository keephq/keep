import React, { useEffect, useState } from "react";
import { ReactFlow, Background, Controls, EdgeTypes as EdgeTypesType, Edge, useReactFlow } from "@xyflow/react";
import CustomNode from "./CustomNode";
import CustomEdge from "./CustomEdge";
import useWorkflowInitialization from "utils/hooks/useWorkflowInitialization";
import DragAndDropSidebar from "./ToolBox";
import { Provider } from "app/providers/providers";
import ReactFlowEditor from "./ReactFlowEditor";
import { Definition } from 'sequential-workflow-designer';
import "@xyflow/react/dist/style.css";
import { WrappedDefinition } from "sequential-workflow-designer-react";


const nodeTypes = { custom: CustomNode as any };
const edgeTypes: EdgeTypesType = { "custom-edge": CustomEdge as React.ComponentType<any> };

const ReactFlowBuilder = ({
  workflow,
  loadedAlertFile,
  providers,
  toolboxConfiguration,
  definition,
  onDefinitionChange
}: {
  workflow: string | undefined;
  loadedAlertFile: string | null;
  providers: Provider[];
  toolboxConfiguration: Record<string, any>;
  definition:  WrappedDefinition<Definition>;
  onDefinitionChange:(def: WrappedDefinition<Definition>) => void;
}) => {
  
  const {
    nodes,
    edges,
    isLoading,
    selectedNode,
    onEdgesChange,
    onNodesChange,
    onConnect,
    onDragOver,
    onDrop,
  } = useWorkflowInitialization(workflow, 
    loadedAlertFile,
     providers,
      definition,
      onDefinitionChange,
      toolboxConfiguration,
    );

  return (
    <div className="sqd-designer-react">
      <div className="sqd-designer sqd-theme-light sqd-layout-desktop">
        <DragAndDropSidebar isDraggable={false}/>
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
