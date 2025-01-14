import { Metadata } from "next";
import WorkflowDetailPage from "./workflow-detail-page";
import { getWorkflowWithRedirectSafe } from "@/shared/api/workflows";

export default async function Page({
  params,
}: {
  params: { workflow_id: string };
}) {
  const initialData = await getWorkflowWithRedirectSafe(params.workflow_id);
  return <WorkflowDetailPage params={params} initialData={initialData} />;
}

export const metadata: Metadata = {
  title: "Keep - Workflow Executions",
  description: "View and manage workflow executions.",
};
