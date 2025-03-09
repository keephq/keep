"use client";

import { useState, useEffect } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import { Provider } from "@/shared/api/providers";
import ReactFlowBuilder from "@/features/workflows/builder/ui/ReactFlowBuilder";
import { useWorkflowStore } from "@/entities/workflows";
import { KeepLoader } from "@/shared/ui";
import {
  parseWorkflow,
  wrapDefinitionV2,
} from "@/entities/workflows/lib/parser";
import MonacoYAMLEditor from "@/shared/ui/YAMLCodeblock/ui/MonacoYAMLEditor";
import { ResizableColumns } from "@/shared/ui";

interface Props {
  workflowRaw: string;
}

export function PublicWorkflowBuilder({ workflowRaw }: Props) {
  const {
    definition,
    setDefinition,
    isLoading,
    setIsLoading,
    reset,
    initializeWorkflow,
    setProviders,
  } = useWorkflowStore();

  // Mock providers for display
  const mockProviders: Provider[] = [
    {
      config: {},
      installed: false,
      linked: false,
      last_alert_received: "",
      details: { authentication: {}, name: "" },
      id: "jira",
      display_name: "Jira",
      can_notify: false,
      can_query: false,
      type: "jira",
      tags: [],
      validatedScopes: {},
      pulling_available: false,
      pulling_enabled: true,
      categories: ["Ticketing"],
      coming_soon: false,
      health: false,
    },
    {
      config: {},
      installed: false,
      linked: false,
      last_alert_received: "",
      details: { authentication: {}, name: "" },
      id: "slack",
      display_name: "Slack",
      can_notify: false,
      can_query: false,
      type: "slack",
      tags: [],
      validatedScopes: {},
      pulling_available: false,
      pulling_enabled: true,
      categories: ["Collaboration"],
      coming_soon: false,
      health: false,
    },
  ];

  useEffect(() => {
    setProviders(mockProviders);
  }, [setProviders]);

  useEffect(() => {
    setIsLoading(true);
    try {
      const parsedDefinition = parseWorkflow(workflowRaw, mockProviders);
      setDefinition(
        wrapDefinitionV2({
          ...parsedDefinition,
          isValid: true,
        })
      );
      initializeWorkflow(null, {
        providers: mockProviders,
        installedProviders: [],
      });
    } catch (error) {
      console.error("Failed to load workflow:", error);
    }
    setIsLoading(false);

    return () => {
      reset();
    };
  }, [workflowRaw, setDefinition, setIsLoading, reset, initializeWorkflow]);

  if (isLoading) {
    return <KeepLoader loadingText="Loading workflow preview..." />;
  }

  return (
    <ResizableColumns initialLeftWidth={33}>
      <>
        <MonacoYAMLEditor
          workflowRaw={workflowRaw}
          filename="workflow-preview"
          readOnly={true}
          data-testid="public-wf-yaml-editor"
        />
      </>
      <>
        <ReactFlowProvider>
          <ReactFlowBuilder />
        </ReactFlowProvider>
      </>
    </ResizableColumns>
  );
}
