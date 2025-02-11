import React from "react";
import {
  ReactFlow,
  Background,
  Controls,
  EdgeTypes as EdgeTypesType,
} from "@xyflow/react";
import CustomNode from "./CustomNode";
import CustomEdge from "./CustomEdge";
import useWorkflowInitialization from "@/utils/hooks/useWorkflowInitialization";
import DragAndDropSidebar from "./ToolBox";
import { Provider } from "@/app/(keep)/providers/providers";
import ReactFlowEditor from "./ReactFlowEditor";
import "@xyflow/react/dist/style.css";
import { getToolboxConfiguration } from "./utils";
import Loading from "../../loading";

const nodeTypes = { custom: CustomNode as any };
const edgeTypes: EdgeTypesType = {
  "custom-edge": CustomEdge as React.ComponentType<any>,
};

const ReactFlowBuilder = ({
  workflowId,
  providers,
  installedProviders,
}: {
  workflowId: string | null;
  providers: Provider[] | undefined | null;
  installedProviders: Provider[] | undefined | null;
}) => {
  const toolboxConfiguration = getToolboxConfiguration(providers ?? []);
  const {
    nodes,
    edges,
    isLayouted,
    onEdgesChange,
    onNodesChange,
    onConnect,
    onDragOver,
    onDrop,
  } = useWorkflowInitialization(workflowId, toolboxConfiguration);

  return (
    <div className="h-[inherit] rounded-lg">
      <div className="h-full sqd-theme-light sqd-layout-desktop">
        <DragAndDropSidebar isDraggable={false} />
        {isLayouted ? (
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
        ) : (
          <Loading loadingText="Initializing workflow builder..." />
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
