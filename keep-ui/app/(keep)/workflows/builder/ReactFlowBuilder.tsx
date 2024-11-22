import React, { useEffect, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  EdgeTypes as EdgeTypesType,
  Edge,
  useReactFlow,
} from "@xyflow/react";
import CustomNode from "./CustomNode";
import CustomEdge from "./CustomEdge";
import useWorkflowInitialization from "utils/hooks/useWorkflowInitialization";
import DragAndDropSidebar from "./ToolBox";
import { Provider } from "@/app/(keep)/providers/providers";
import ReactFlowEditor from "./ReactFlowEditor";
import "@xyflow/react/dist/style.css";
import { ReactFlowDefinition, V2Step, Definition } from "./builder-store";

const nodeTypes = { custom: CustomNode as any };
const edgeTypes: EdgeTypesType = {
  "custom-edge": CustomEdge as React.ComponentType<any>,
};

const ReactFlowBuilder = ({
  providers,
  installedProviders,
  toolboxConfiguration,
  definition,
  onDefinitionChange,
  validatorConfiguration,
}: {
  providers: Provider[] | undefined | null;
  installedProviders: Provider[] | undefined | null;
  toolboxConfiguration: Record<string, any>;
  definition: any;
  validatorConfiguration: {
    step: (
      step: V2Step,
      parent?: V2Step,
      defnition?: ReactFlowDefinition
    ) => boolean;
    root: (def: Definition) => boolean;
  };
  onDefinitionChange: (def: Definition) => void;
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
  } = useWorkflowInitialization(definition, toolboxConfiguration);

  return (
    <div className="sqd-designer-react">
      <div className="sqd-designer sqd-theme-light sqd-layout-desktop">
        <DragAndDropSidebar isDraggable={false} />
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
            <Controls orientation="horizontal" />
            <Background />
          </ReactFlow>
        )}
        <ReactFlowEditor
          providers={providers}
          installedProviders={installedProviders}
          onDefinitionChange={onDefinitionChange}
          validatorConfiguration={validatorConfiguration}
        />
      </div>
    </div>
  );
};

export default ReactFlowBuilder;
