import { Metadata } from "next";
import PageClient from "../page.client";
import { createServerApiClient } from "@/shared/api/server";

type WorkflowRawResponse = {
  workflow_raw: string;
};

export default async function PageWithId({
  params,
}: {
  params: { workflowId: string };
}) {
  const api = await createServerApiClient();
  const text = await api.get<WorkflowRawResponse>(
    `/workflows/${params.workflowId}/raw`,
    {
      cache: "no-store",
    }
  );
  return (
    <PageClient workflow={text.workflow_raw} workflowId={params.workflowId} />
  );
}

export const metadata: Metadata = {
  title: "Keep - Workflow Builder",
  description: "Build workflows with a UI builder.",
};
