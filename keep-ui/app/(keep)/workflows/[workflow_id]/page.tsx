import { Metadata } from "next";
import WorkflowDetailPage from "./workflow-detail-page";
import { getWorkflowWithRedirectSafe } from "@/shared/api/workflows";

export default async function Page(props: {
  params: Promise<{ workflow_id: string }>;
}) {
  const params = await props.params;
  const initialData = await getWorkflowWithRedirectSafe(params.workflow_id);
  return <WorkflowDetailPage params={params} initialData={initialData} />;
}

export const metadata: Metadata = {
  title: "Keep - Workflow Executions",
  description: "View and manage workflow executions.",
};
