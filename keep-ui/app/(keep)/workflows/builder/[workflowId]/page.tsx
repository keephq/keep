import { Metadata } from "next";
import { WorkflowBuilderWidget } from "@/widgets/workflow-builder";
import { createServerApiClient } from "@/shared/api/server";

type WorkflowRawResponse = {
  workflow_raw: string;
};

export default async function PageWithId(
  props: {
    params: Promise<{ workflowId: string }>;
  }
) {
  const params = await props.params;
  const api = await createServerApiClient();
  const text = await api.get<WorkflowRawResponse>(
    `/workflows/${params.workflowId}/raw`,
    {
      cache: "no-store",
    }
  );
  return (
    <WorkflowBuilderWidget
      workflowRaw={text.workflow_raw}
      workflowId={params.workflowId}
      standalone={true}
    />
  );
}

export const metadata: Metadata = {
  title: "Keep - Workflow Builder",
  description: "Build workflows with a UI builder.",
};
