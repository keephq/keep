"use client";

import React, { useEffect } from "react";
import { useWorkflowStore } from "./workflow-store";
import { Workflow } from "@/shared/api/workflows";
import { useProviders } from "@/utils/hooks/useProviders";

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
  } = useWorkflowStore();
  const initializedWorkflowId = useWorkflowStore((s) => s.v2Properties.id);
  const { data: providers } = useProviders();

  useEffect(() => {
    if (
      !workflow?.workflow_raw ||
      !providers ||
      initializedWorkflowId === workflow.id
    ) {
      return;
    }

    // Initialize workflow
    initialize(workflow.workflow_raw, providers.providers);

    return cleanup;
  }, [
    workflow,
    providers,
    initialize,
    cleanup,
    setToolBoxConfig,
    updateV2Properties,
    setSelectedNode,
  ]);

  return children;
}
