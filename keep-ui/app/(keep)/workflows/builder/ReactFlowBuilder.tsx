import React, { useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  EdgeTypes as EdgeTypesType,
  useReactFlow,
} from "@xyflow/react";
import CustomNode from "./CustomNode";
import CustomEdge from "./CustomEdge";
import DragAndDropSidebar from "./ToolBox";
import { Provider } from "@/app/(keep)/providers/providers";
import ReactFlowEditor from "./ReactFlowEditor";
import "@xyflow/react/dist/style.css";
import Loading from "../../loading";
import useStore from "./builder-store";

const nodeTypes = { custom: CustomNode as any };
const edgeTypes: EdgeTypesType = {
  "custom-edge": CustomEdge as React.ComponentType<any>,
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
  } = useStore();

  const { screenToFlowPosition } = useReactFlow();

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      // TODO: do we use drag and drop?
      // TODO: fix type;
      onDrop(event as unknown as DragEvent, screenToFlowPosition);
    },
    [screenToFlowPosition]
  );

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
            onDrop={handleDrop}
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
