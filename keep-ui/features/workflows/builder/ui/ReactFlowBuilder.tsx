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
import { WorkflowEdge } from "./WorkflowEdge";
import ReactFlowEditor from "./Editor/ReactFlowEditor";
import { FlowNode, useWorkflowStore } from "@/entities/workflows";
import { KeepLoader } from "@/shared/ui";
import "@xyflow/react/dist/style.css";

const nodeTypes = { custom: WorkflowNode as any };
const edgeTypes: EdgeTypesType = {
  "custom-edge": WorkflowEdge as React.ComponentType<any>,
};

const defaultFitViewOptions: FitViewOptions = {
  padding: 0.1,
  minZoom: 0.1,
};

const ReactFlowBuilder = () => {
  const {
    nodes,
    edges,
    isLayouted,
    onEdgesChange,
    onNodesChange,
    onConnect,
    onDragOver,
    onDrop,
    selectedNode,
    selectedEdge,
  } = useWorkflowStore();

  const { screenToFlowPosition } = useReactFlow();

  const reactFlowInstanceRef = useRef<ReactFlowInstance<FlowNode, Edge> | null>(
    null
  );

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      // TODO: do we use drag and drop?
      // TODO: fix type;
      onDrop(event as unknown as DragEvent, screenToFlowPosition);
    },
    [screenToFlowPosition]
  );

  useEffect(
    function fitViewOnLayoutAndEditorOpen() {
      if (!selectedEdge && !selectedNode) {
        return;
      }
      const nodesToFit: { id: string }[] = [];
      if (selectedNode) {
        nodesToFit.push({ id: selectedNode });
      }
      if (selectedEdge) {
        const edge = reactFlowInstanceRef.current?.getEdge(selectedEdge);
        if (edge) {
          nodesToFit.push({ id: edge.source }, { id: edge.target });
        }
      }

      // setTimeout is used to be sure that reactFlow will handle the fitView correctly
      setTimeout(() => {
        reactFlowInstanceRef.current?.fitView({
          padding: 0.2,
          nodes: nodesToFit,
          duration: 150,
          maxZoom: 0.8,
        });
      }, 0);
    },
    [selectedEdge, selectedNode]
  );
  return (
    <div className="h-full sqd-theme-light sqd-layout-desktop flex">
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
      <ReactFlowEditor />
    </div>
  );
};

export default ReactFlowBuilder;
