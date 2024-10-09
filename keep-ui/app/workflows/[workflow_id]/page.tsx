"use client";
import WorkflowDetailPage from "./executions";

export default function Page({ params }: { params: { workflow_id: string } }) {
  return <WorkflowDetailPage params={params} />;
}
