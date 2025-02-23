"use client";

import { CopilotKit } from "@copilotkit/react-core";
import {
  WorkflowBuilderWidget,
  WorkflowBuilderWidgetProps,
} from "./workflow-builder-widget";
import { useConfig } from "@/utils/hooks/useConfig";

export function WorkflowBuilderWidgetSafe(props: WorkflowBuilderWidgetProps) {
  const { data: config } = useConfig();

  if (!config?.OPEN_AI_API_KEY_SET) {
    return <WorkflowBuilderWidget />;
  }

  return (
    <CopilotKit runtimeUrl="/api/copilotkit">
      <WorkflowBuilderWidget {...props} />
    </CopilotKit>
  );
}
