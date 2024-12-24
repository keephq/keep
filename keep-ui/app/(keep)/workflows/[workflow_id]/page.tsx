import { Metadata } from "next";
import WorkflowDetailPage from "./executions";

export default function Page({ params }: { params: { workflow_id: string } }) {
  return <WorkflowDetailPage params={params} />;
}

export const metadata: Metadata = {
  title: "Keep - Workflow Executions",
  description: "View and manage workflow executions.",
};
