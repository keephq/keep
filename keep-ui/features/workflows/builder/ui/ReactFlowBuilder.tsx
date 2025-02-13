import React, { useCallback, useEffect, useRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  EdgeTypes as EdgeTypesType,
  useReactFlow,
  FitViewOptions,
  ReactFlowInstance,
  Edge,
} from "@xyflow/react";
import WorkflowNode from "./WorkflowNode";
import CustomEdge from "./WorkflowEdge";
import DragAndDropSidebar from "./ToolBox";
import { Provider } from "@/app/(keep)/providers/providers";
import ReactFlowEditor from "./ReactFlowEditor";
import "@xyflow/react/dist/style.css";
import { FlowNode, useWorkflowStore } from "@/entities/workflows";
import { KeepLoader } from "@/shared/ui";

const nodeTypes = { custom: WorkflowNode as any };
const edgeTypes: EdgeTypesType = {
  "custom-edge": CustomEdge as React.ComponentType<any>,
};

const defaultFitViewOptions: FitViewOptions = {
  padding: 0.1,
  minZoom: 0.1,
};

const ReactFlowBuilder = ({
  providers,
  installedProviders,
}: {
  // TODO: move providers from props to ReactFlowEditor itself
  providers: Provider[] | undefined | null;
  installedProviders: Provider[] | undefined | null;
}) => {
  const {
    nodes,
    edges,
    isLayouted,
    onEdgesChange,
    onNodesChange,
    onConnect,
    onDragOver,
    onDrop,
    openGlobalEditor,
    selectedEdge,
  } = useWorkflowStore();

  const { screenToFlowPosition } = useReactFlow();

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      // TODO: do we use drag and drop?
      // TODO: fix type;
      onDrop(event as unknown as DragEvent, screenToFlowPosition);
    },
    [screenToFlowPosition]
  );

  const reactFlowInstanceRef = useRef<ReactFlowInstance<FlowNode, Edge> | null>(
    null
  );
  useEffect(
    function fitViewOnLayoutAndEditorOpen() {
      if (!isLayouted) {
        return;
      }
      reactFlowInstanceRef.current?.fitView();
    },
    [isLayouted, openGlobalEditor]
  );
  useEffect(
    function fitViewOnToolboxOpenClose() {
      reactFlowInstanceRef.current?.fitView();
    },
    [selectedEdge]
  );

  return (
    <div className="h-[inherit] rounded-lg">
      <div className="h-full sqd-theme-light sqd-layout-desktop flex">
        <DragAndDropSidebar isDraggable={false} />
        {isLayouted ? (
          <ReactFlow
            fitView
            nodes={nodes}
            edges={edges}
            fitViewOptions={defaultFitViewOptions}
            maxZoom={0.8}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onDrop={handleDrop}
            onDragOver={onDragOver}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            onInit={(instance) => {
              reactFlowInstanceRef.current = instance;
            }}
          >
            <Controls orientation="horizontal" />
            <Background />
          </ReactFlow>
        ) : (
          <KeepLoader loadingText="Initializing workflow builder..." />
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
