import { useEffect, useState, useCallback } from "react";
import { useReactFlow } from "@xyflow/react";
import { useWorkflowStore } from "@/app/(keep)/workflows/builder/workflow-store";
import {
  FlowNode,
  ReactFlowDefinition,
} from "@/app/(keep)/workflows/builder/types";

const useWorkflowInitialization = (
  definition: ReactFlowDefinition,
  toolboxConfiguration: Record<string, any>
) => {
  const {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    onDragOver,
    onDrop,
    updateV2Properties,
    openGlobalEditor,
    selectedNode,
    setToolBoxConfig,
    isLayouted,
    changes,
    setSelectedNode,
  } = useWorkflowStore();

  const [isLoading, setIsLoading] = useState(true);
  const { screenToFlowPosition } = useReactFlow();

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      onDrop(event, () => screenToFlowPosition({ x: 0, y: 0 }));
    },
    [screenToFlowPosition]
  );

  useEffect(() => {
    const initializeWorkflow = async () => {
      setIsLoading(true);
      let parsedWorkflow = definition?.value;
      const name =
        parsedWorkflow?.properties?.name || parsedWorkflow?.properties?.id;

      if (changes === 0) {
        setSelectedNode(null);
        updateV2Properties({ ...(parsedWorkflow?.properties ?? {}), name });
        setToolBoxConfig(toolboxConfiguration);
      }
      setIsLoading(false);
    };

    initializeWorkflow();
  }, [changes]);

  return {
    nodes,
    edges,
    isLoading,
    onNodesChange,
    onEdgesChange,
    onConnect,
    onDragOver,
    onDrop: handleDrop,
    openGlobalEditor,
    selectedNode,
    toolboxConfiguration,
    isLayouted,
  };
};

export default useWorkflowInitialization;
