'use client';
import { use } from "react";
import WorkflowDetailPage from "./executions";

export default function Page(props:{params: Promise<{ workflow_id: string }>}) {
  const params = use(props.params);
  return <WorkflowDetailPage params={params}/>;
}
