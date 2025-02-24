import {
  getYamlActionFromAction,
  getYamlStepFromStep,
} from "@/entities/workflows/lib/parser";
import {
  FlowNode,
  V2ActionStep,
  V2Step,
  V2StepStep,
  V2StepTrigger,
} from "@/entities/workflows/model/types";
import { Edge } from "@xyflow/react";

export function getYamlFromStep(step: V2Step | V2StepTrigger) {
  try {
    if (step.componentType === "task" && step.type.startsWith("step-")) {
      return getYamlStepFromStep(step as V2StepStep);
    }
    if (step.componentType === "task" && step.type.startsWith("action-")) {
      return getYamlActionFromAction(step as V2ActionStep);
    }
    if (step.componentType === "trigger") {
      return {
        type: step.type,
        ...step.properties,
      };
    }
    // TODO: add other types
    return null;
  } catch (error) {
    console.error(error);
    return null;
  }
}

export function getWorkflowSummaryForCopilot(nodes: FlowNode[], edges: Edge[]) {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      nextStepId: n.nextStepId,
      prevStepId: n.prevStepId,
      ...n.data,
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
    })),
  };
}

export function getErrorMessage(e: unknown, defaultMessage?: string) {
  if (e instanceof Error) {
    return e.message;
  }
  return defaultMessage ?? "Unknown error";
}
