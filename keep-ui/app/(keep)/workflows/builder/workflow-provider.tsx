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
  const initialize = useWorkflowStore((s) => s.initialize);
  const cleanup = useWorkflowStore((s) => s.cleanup);
  const { data: providers } = useProviders();

  useEffect(() => {
    if (!workflow?.workflow_raw || !providers) {
      return;
    }
    initialize(workflow?.workflow_raw, providers.providers);
    return cleanup;
  }, [workflow, providers, initialize, cleanup]);

  return children;
}
