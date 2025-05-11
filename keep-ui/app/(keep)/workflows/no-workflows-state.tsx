"use client";

import { WorkflowTemplates } from "./create-workflow-modal";
import { InitialFacetsData } from "@/features/filter/api";

export function NoWorkflowsState({}: {
  initialFacetsData?: InitialFacetsData;
}) {
  return (
    <>
      <p className="text-3xl font-bold mb-3">Create your first workflow</p>
      <WorkflowTemplates></WorkflowTemplates>
    </>
  );
}
