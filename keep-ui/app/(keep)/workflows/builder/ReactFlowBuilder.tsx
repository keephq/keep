import React from "react";
import {
  ReactFlow,
  Background,
  Controls,
  EdgeTypes as EdgeTypesType,
} from "@xyflow/react";
import CustomNode from "./CustomNode";
import CustomEdge from "./CustomEdge";
import useWorkflowInitialization from "utils/hooks/useWorkflowInitialization";
import DragAndDropSidebar from "./ToolBox";
import { Provider } from "@/app/(keep)/providers/providers";
import ReactFlowEditor from "./ReactFlowEditor";
import "@xyflow/react/dist/style.css";

import {
  Definition,
  ReactFlowDefinition,
  ToolboxConfiguration,
  V2Step,
} from "@/app/(keep)/workflows/builder/types";

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
  toolboxConfiguration: ToolboxConfiguration;
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
