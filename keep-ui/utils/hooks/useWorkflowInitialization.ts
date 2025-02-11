import { useEffect, useCallback } from "react";
import { useReactFlow } from "@xyflow/react";
import useStore from "@/app/(keep)/workflows/builder/builder-store";

const useWorkflowInitialization = (
  workflowId: string | null,
  toolboxConfiguration: Record<string, any>
) => {
  const {
    nodes,
    edges,
    setNodes,
    onNodesChange,
    onEdgesChange,
    onConnect,
    onDragOver,
    onDrop,
    openGlobalEditor,
    selectedNode,
    isLayouted,
    changes,
    initializeWorkflow,
    isLoading,
  } = useStore();

  const { screenToFlowPosition } = useReactFlow();

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      onDrop(event, screenToFlowPosition);
    },
    [screenToFlowPosition]
  );

  useEffect(() => {
    if (changes === 0) {
      initializeWorkflow(workflowId, toolboxConfiguration);
    }
  }, [changes]);

  return {
    nodes,
    edges,
    isLoading,
    onNodesChange: onNodesChange,
    onEdgesChange: onEdgesChange,
    onConnect: onConnect,
    onDragOver: onDragOver,
    onDrop: handleDrop,
    openGlobalEditor,
    selectedNode,
    setNodes,
    toolboxConfiguration,
    isLayouted,
  };
};

export default useWorkflowInitialization;
