"use client";

import React, { useEffect, useCallback } from "react";
import { useWorkflowStore } from "./workflow-store";
import { Workflow } from "@/shared/api/workflows";
import { useProviders } from "@/utils/hooks/useProviders";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
import { showErrorToast } from "@/shared/ui";

interface WorkflowProviderProps {
  workflow?: Workflow;
  children: React.ReactNode;
}

export function WorkflowProvider({
  workflow,
  children,
}: WorkflowProviderProps) {
  const {
    initialize,
    cleanup,
    setToolBoxConfig,
    updateV2Properties,
    setSelectedNode,
    setSaveWorkflow,
  } = useWorkflowStore();
  const { updateWorkflow, createWorkflow } = useWorkflowActions();
  const { data: providers } = useProviders();
  const initializedWorkflowId = useWorkflowStore((s) => s.workflowId);

  // Move save workflow logic to provider
  const handleSaveWorkflow = useCallback(async () => {
    const { isPendingSync, errorNodes, definition, workflowId } =
      useWorkflowStore.getState();
    if (isPendingSync) {
      showErrorToast("Cannot save while changes are pending");
      return;
    }

    // if (errorNodes.length > 0 || !definition.isValid) {
    //   showErrorToast("Cannot save invalid workflow");
    //   return;
    // }

    if (workflowId) {
      await updateWorkflow(workflowId, definition.value);
    } else {
      await createWorkflow(definition.value);
    }
  }, [updateWorkflow, createWorkflow]);

  // Use setSaveWorkflow instead of setState
  useEffect(() => {
    setSaveWorkflow(handleSaveWorkflow);
  }, [setSaveWorkflow, handleSaveWorkflow]);

  useEffect(() => {
    console.log(
      "xxx workflowProvider",
      workflow,
      initializedWorkflowId,
      providers
    );
    if (
      workflow &&
      workflow.workflow_raw &&
      providers &&
      initializedWorkflowId !== workflow.id
    ) {
      // Initialize workflow
      initialize(workflow.workflow_raw, providers.providers, workflow.id);
    }
  }, [
    workflow,
    providers,
    initialize,
    setToolBoxConfig,
    updateV2Properties,
    setSelectedNode,
    initializedWorkflowId,
  ]);

  useEffect(function resetZustandStateOnUnMount() {
    return () => {
      console.log("xxx call cleanup");
      cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return children;
}
